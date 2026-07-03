"""LocalProvider — fully offline provider used for dev, demos, CI and the
eval harness.

- OCR: pdfplumber text extraction with real per-line bounding boxes (PDF
  point space, 72 dpi), emitted in the same block shape as Mistral OCR 4.
- Classification: keyword scoring against the schema registry.
- Extraction: deterministic label-anchored extraction ("Label: value" lines,
  section-based arrays, pipe-table rent rolls) with genuine citations
  (text_span + page + bbox). Required fields that cannot be anchored are
  ABSTAINED, never guessed — mirroring the production abstention design.

This provider processes digital-text PDFs only (no raster OCR); scanned
documents require the Mistral provider.
"""

from __future__ import annotations

import io
import re
import unicodedata
from typing import Any

import pdfplumber

from app.providers.base import (
    ClassificationResult,
    ExtractedField,
    OcrBlock,
    OcrPage,
    Provider,
)
from dd_schemas import DocSchema, FieldSpec

DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
NUM_RE = re.compile(r"\d{1,3}(?:[.\s ]\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?")


def _norm(s: str) -> str:
    """Casefold + strip accents for label matching."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.casefold().strip()


def parse_number(text: str) -> float | None:
    m = NUM_RE.search(text)
    if not m:
        return None
    raw = m.group(0).replace(" ", " ")
    if "," in raw:
        raw = raw.replace(".", "").replace(" ", "").replace(",", ".")
    elif raw.count(".") == 1 and len(raw.split(".")[1]) != 3:
        raw = raw.replace(" ", "")  # plain decimal like 4.8
    else:
        raw = raw.replace(".", "").replace(" ", "")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_date(text: str) -> str | None:
    m = DATE_RE.search(text)
    if not m:
        iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
        if iso:
            return iso.group(0)
        return None
    d, mo, y = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


class LocalProvider:
    name = "local"
    model_version = "local-deterministic-1"
    prompt_version = "n/a"

    # ------------------------------------------------------------------ OCR
    def ocr(self, pdf_bytes: bytes, filename: str) -> list[OcrPage]:
        pages: list[OcrPage] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                lines = page.extract_text_lines() or []
                blocks: list[OcrBlock] = []
                md_lines: list[str] = []
                for ln in lines:
                    text = (ln.get("text") or "").strip()
                    if not text:
                        continue
                    btype = "title" if (text.isupper() and len(text) < 60) else "text"
                    if "|" in text:
                        btype = "table"
                    blocks.append(
                        OcrBlock(
                            type=btype,
                            x1=float(ln["x0"]),
                            y1=float(ln["top"]),
                            x2=float(ln["x1"]),
                            y2=float(ln["bottom"]),
                            content=text,
                        )
                    )
                    md_lines.append(f"## {text}" if btype == "title" else text)
                pages.append(
                    OcrPage(
                        page_number=i,
                        markdown="\n".join(md_lines),
                        blocks=blocks,
                        width=int(page.width),
                        height=int(page.height),
                        dpi=72,
                        avg_confidence=1.0,
                        min_confidence=1.0,
                    )
                )
        return pages

    # --------------------------------------------------------- classification
    def classify(self, pages: list[OcrPage], schemas: list[DocSchema]) -> ClassificationResult:
        text = _norm(" ".join(p.markdown for p in pages[:2]))
        best_key, best_score = "unknown", 0.0
        best_lang = "unknown"
        for schema in schemas:
            hits = sum(1 for kw in schema.classification_keywords if _norm(kw) in text)
            if not schema.classification_keywords:
                continue
            score = hits / len(schema.classification_keywords)
            if score > best_score:
                best_key, best_score, best_lang = schema.key, score, schema.language
        if best_score < 0.25:
            return ClassificationResult(doc_type="unknown", language=best_lang, confidence=best_score)
        return ClassificationResult(
            doc_type=best_key, language=best_lang, confidence=min(0.99, 0.5 + best_score / 2)
        )

    # -------------------------------------------------------------- extraction
    def extract(self, pages: list[OcrPage], schema: DocSchema) -> list[ExtractedField]:
        fields: list[ExtractedField] = []
        emitted: set[str] = set()

        if schema.key == "rent_roll":
            fields.extend(self._extract_rent_roll_units(pages))
            emitted.update(f.field_path for f in fields)

        array_specs = [f for f in schema.fields if f.type == "array" and f.path in
                       ("cargas", "titularidad", "notas_marginales")]
        for spec in array_specs:
            got = self._extract_section_array(pages, spec)
            for f in got:
                if f.field_path not in emitted:
                    fields.append(f)
                    emitted.add(f.field_path)

        for spec in schema.fields:
            if spec.path in emitted or spec.type == "array":
                continue
            hit = self._anchor_field(pages, spec)
            if hit is not None:
                fields.append(hit)
                emitted.add(spec.path)
            elif spec.required:
                fields.append(
                    ExtractedField(
                        field_path=spec.path, value=None, text_span=None,
                        page_number=None, bbox=None, confidence=0.0,
                        abstained=True, method="label_anchor",
                    )
                )
        return fields

    # -- label-anchored scalar fields
    def _anchor_field(self, pages: list[OcrPage], spec: FieldSpec) -> ExtractedField | None:
        # Two passes: strict ("Label: value" — colon right after the label)
        # first, so 'SIREN:' never swallows 'SIREN du bailleur:'; loose
        # (label starts the line, colon later) as fallback.
        for strict in (True, False):
            for page in pages:
                for block in page.blocks:
                    content = block.content
                    ncontent = _norm(content)
                    for label in spec.labels:
                        nlabel = _norm(label)
                        if not ncontent.startswith(nlabel):
                            continue
                        rest = content[len(label):].lstrip(" \t")
                        if rest.startswith(":"):
                            raw = rest[1:].strip()
                        elif not strict and ":" in content:
                            raw = content.split(":", 1)[1].strip()
                        else:
                            continue
                        value = self._parse_value(raw, spec)
                        if value is None:
                            continue
                        confidence = 0.95 if strict else 0.8
                        return ExtractedField(
                            field_path=spec.path, value=value, text_span=content,
                            page_number=page.page_number, bbox=block.bbox(),
                            confidence=confidence, method="label_anchor",
                        )
        return None

    def _parse_value(self, raw: str, spec: FieldSpec) -> Any:
        if not raw:
            return None
        if spec.enum:
            tokens = re.findall(r"[A-Za-z]+", raw.upper())
            for member in spec.enum:
                if member.upper() in tokens:
                    return member
            return None
        if spec.type in ("money", "number"):
            return parse_number(raw)
        if spec.type == "date":
            return parse_date(raw)
        if spec.type == "boolean":
            return _norm(raw) in ("si", "sí", "oui", "yes", "true")
        return raw

    # -- section-based arrays (nota simple: CARGAS / TITULARIDAD / NOTAS)
    def _extract_section_array(
        self, pages: list[OcrPage], spec: FieldSpec
    ) -> list[ExtractedField]:
        section_labels = {_norm(lbl) for lbl in spec.labels}
        collecting = False
        item_lines: list[tuple[int, OcrBlock]] = []
        header: tuple[int, OcrBlock] | None = None
        for page in pages:
            for block in page.blocks:
                ncontent = _norm(block.content)
                if block.type == "title" or block.content.isupper():
                    if any(ncontent.startswith(lbl) for lbl in section_labels):
                        collecting = True
                        header = (page.page_number, block)
                        continue
                    if collecting:
                        collecting = False
                    continue
                if collecting:
                    item_lines.append((page.page_number, block))
        if header is None:
            return []

        out: list[ExtractedField] = []
        if spec.path == "cargas":
            items, none_of_them = [], False
            for pno, block in item_lines:
                if "libre de cargas" in _norm(block.content):
                    none_of_them = True
                    break
                item = self._parse_carga(block.content)
                if item:
                    items.append((item, pno, block))
            value = [] if none_of_them else [it for it, _, _ in items]
            out.append(
                ExtractedField(
                    field_path="cargas", value=value,
                    text_span=header[1].content, page_number=header[0],
                    bbox=header[1].bbox(), confidence=0.9, method="label_anchor",
                )
            )
            if items and not none_of_them:
                first, pno, block = items[0]
                for sub, val in (
                    ("tipo", first.get("tipo")),
                    ("importe", first.get("importe")),
                    ("acreedor", first.get("acreedor")),
                ):
                    if val is not None:
                        out.append(
                            ExtractedField(
                                field_path=f"cargas[0].{sub}", value=val,
                                text_span=block.content, page_number=pno,
                                bbox=block.bbox(), confidence=0.85,
                                method="label_anchor",
                            )
                        )
        elif spec.path == "titularidad":
            value = [b.content for _, b in item_lines]
            out.append(
                ExtractedField(
                    field_path="titularidad", value=value,
                    text_span=header[1].content, page_number=header[0],
                    bbox=header[1].bbox(), confidence=0.85, method="label_anchor",
                )
            )
        elif spec.path == "notas_marginales":
            notes = [
                b.content for _, b in item_lines if "sin notas" not in _norm(b.content)
            ]
            out.append(
                ExtractedField(
                    field_path="notas_marginales", value=notes,
                    text_span=header[1].content, page_number=header[0],
                    bbox=header[1].bbox(), confidence=0.85, method="label_anchor",
                )
            )
        return out

    def _parse_carga(self, line: str) -> dict[str, Any] | None:
        nline = _norm(line)
        tipo = None
        for t in ("hipoteca", "embargo", "servidumbre", "afeccion fiscal",
                  "condicion resolutoria"):
            if nline.startswith(t):
                tipo = t.replace("afeccion fiscal", "afección fiscal").replace(
                    "condicion resolutoria", "condición resolutoria")
                break
        if tipo is None:
            return None
        item: dict[str, Any] = {"tipo": tipo, "raw": line}
        m = re.search(r"a favor de\s+([^,;]+)", line, flags=re.IGNORECASE)
        if m:
            item["acreedor"] = m.group(1).strip()
        money = re.search(
            r"(?:principal|importe|responsabilidad)[^\d]*(" + NUM_RE.pattern + ")",
            line, flags=re.IGNORECASE,
        )
        if money:
            item["importe"] = parse_number(money.group(1))
        d = parse_date(line)
        if d:
            item["fecha"] = d
        r = re.search(r"rango\s+(\d+)", line, flags=re.IGNORECASE)
        if r:
            item["rango"] = int(r.group(1))
        return item

    # -- pipe-table rent roll
    RENT_ROLL_COLS = {
        "unit": "unit_id", "unidad": "unit_id", "lot": "unit_id",
        "tenant": "tenant_name", "arrendatario": "tenant_name", "locataire": "tenant_name",
        "use": "use", "uso": "use",
        "area": "area_m2", "surface": "area_m2", "superficie": "area_m2",
        "lease start": "lease_start", "start": "lease_start", "inicio": "lease_start",
        "lease end": "lease_end", "end": "lease_end", "fin": "lease_end",
        "break": "break_date",
        "passing rent": "passing_rent", "rent": "passing_rent", "renta": "passing_rent",
        "frequency": "rent_frequency", "periodicidad": "rent_frequency",
        "index": "index", "indice": "index",
        "deposit": "deposit", "fianza": "deposit",
        "arrears": "arrears", "impagos": "arrears",
    }

    def _extract_rent_roll_units(self, pages: list[OcrPage]) -> list[ExtractedField]:
        header_cols: list[str] | None = None
        units: list[dict[str, Any]] = []
        first_row: tuple[int, OcrBlock] | None = None
        for page in pages:
            for block in page.blocks:
                if "|" not in block.content:
                    continue
                cells = [c.strip() for c in block.content.split("|")]
                if header_cols is None:
                    mapped = [self._map_col(c) for c in cells]
                    if any(m == "unit_id" for m in mapped):
                        header_cols = [m or f"col{i}" for i, m in enumerate(mapped)]
                    continue
                row: dict[str, Any] = {}
                for col, cell in zip(header_cols, cells):
                    if not cell:
                        continue
                    if col in ("area_m2", "passing_rent", "deposit", "arrears"):
                        row[col] = parse_number(cell)
                    elif col in ("lease_start", "lease_end", "break_date"):
                        row[col] = parse_date(cell)
                    else:
                        row[col] = cell
                if row.get("unit_id"):
                    row["vacancy_flag"] = _norm(str(row.get("tenant_name", ""))) in (
                        "vacant", "vacante", "vacant unit", "")
                    units.append(row)
                    if first_row is None:
                        first_row = (page.page_number, block)
        if not units or first_row is None:
            return []
        return [
            ExtractedField(
                field_path="units", value=units,
                text_span=first_row[1].content, page_number=first_row[0],
                bbox=first_row[1].bbox(), confidence=0.9, method="label_anchor",
            )
        ]

    def _map_col(self, cell: str) -> str | None:
        ncell = _norm(cell)
        for key, col in self.RENT_ROLL_COLS.items():
            if key in ncell:
                return col
        return None


_ = Provider  # protocol conformance is structural
