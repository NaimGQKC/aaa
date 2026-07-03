"""MistralProvider — EU-sovereign API phase (La Plateforme: EU data residency
by default; enable Zero Data Retention + signed DPA on the org).

- OCR: POST /v1/ocr (mistral-ocr-latest) with include_blocks; pixel bboxes
  are normalised to PDF point space at ingestion (spec §5.2 pitfall).
- Classification: small model (Ministral) few-shot on first-page markdown.
- Extraction: chat completion with JSON-schema response_format built from the
  schema registry; per-field text_span is fuzzy-matched back to OCR blocks to
  recover page + bbox.

Uses raw HTTPS via httpx (no SDK lock-in); the same request shapes work
against a self-hosted vLLM/xgrammar endpoint by changing base_url — that is
the self-host migration path.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from app.config import get_settings
from app.providers.base import (
    ClassificationResult,
    ExtractedField,
    OcrBlock,
    OcrPage,
)
from app.providers.citations import find_span
from dd_schemas import DocSchema

API_BASE = "https://api.mistral.ai/v1"
PROMPT_VERSION = "extraction-v1"

CLASSIFY_PROMPT = """You classify real-estate documents. Given the first page(s) of a document,
answer with JSON: {{"doc_type": <one of {keys} or "unknown">, "language": <"es"|"fr"|"en">, "confidence": <0..1>}}.

Document types:
{descriptions}

First page(s):
---
{text}
---"""

EXTRACT_SYSTEM = """You are a due-diligence extraction engine for European real-estate documents.
Extract ONLY what the document states. For every field return:
- value: the extracted value (null if absent)
- text_span: the EXACT verbatim source text you read the value from
- confidence: 0..1
- abstained: true when you cannot reliably extract the field (then value must be null)
Never guess. Never paraphrase text_span — it must appear verbatim in the document."""


class MistralProvider:
    name = "mistral"

    def __init__(self) -> None:
        s = get_settings()
        if not s.mistral_api_key:
            raise RuntimeError("DD_PROVIDER=mistral requires MISTRAL_API_KEY")
        self.api_key = s.mistral_api_key
        self.ocr_model = s.mistral_ocr_model
        self.llm_model = s.mistral_llm_model
        self.small_model = s.mistral_small_model
        self.model_version = f"{self.ocr_model}+{self.llm_model}"
        self.prompt_version = PROMPT_VERSION
        self._client = httpx.Client(
            base_url=API_BASE,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=300,
        )

    # ------------------------------------------------------------------ OCR
    def ocr(self, pdf_bytes: bytes, filename: str) -> list[OcrPage]:
        b64 = base64.b64encode(pdf_bytes).decode()
        resp = self._client.post(
            "/ocr",
            json={
                "model": self.ocr_model,
                "document": {
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{b64}",
                },
                "include_blocks": True,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        pages: list[OcrPage] = []
        for i, p in enumerate(data.get("pages", []), start=1):
            dims = p.get("dimensions") or {}
            dpi = int(dims.get("dpi") or 72)
            width_px = int(dims.get("width") or 0)
            height_px = int(dims.get("height") or 0)
            # Normalise pixel coords at `dpi` -> PDF points (72/inch).
            scale = 72.0 / dpi if dpi else 1.0
            blocks = [
                OcrBlock(
                    type=b.get("type", "text"),
                    x1=b.get("top_left_x", 0) * scale,
                    y1=b.get("top_left_y", 0) * scale,
                    x2=b.get("bottom_right_x", 0) * scale,
                    y2=b.get("bottom_right_y", 0) * scale,
                    content=b.get("content", ""),
                )
                for b in (p.get("blocks") or [])
            ]
            conf = p.get("confidence_scores") or {}
            pages.append(
                OcrPage(
                    page_number=p.get("index", i) or i,
                    markdown=p.get("markdown", ""),
                    blocks=blocks,
                    width=int(width_px * scale),
                    height=int(height_px * scale),
                    dpi=72,
                    avg_confidence=float(conf.get("average_page_confidence_score", 1.0)),
                    min_confidence=float(conf.get("minimum_page_confidence_score", 1.0)),
                )
            )
        return pages

    # --------------------------------------------------------- classification
    def classify(self, pages: list[OcrPage], schemas: list[DocSchema]) -> ClassificationResult:
        keys = [s.key for s in schemas]
        descriptions = "\n".join(f"- {s.key}: {s.description}" for s in schemas)
        text = "\n\n".join(p.markdown for p in pages[:2])[:8000]
        out = self._chat_json(
            self.small_model,
            [{"role": "user", "content": CLASSIFY_PROMPT.format(
                keys=keys, descriptions=descriptions, text=text)}],
            schema={
                "type": "object",
                "properties": {
                    "doc_type": {"type": "string"},
                    "language": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["doc_type", "language", "confidence"],
            },
        )
        doc_type = out.get("doc_type", "unknown")
        if doc_type not in keys:
            doc_type = "unknown"
        return ClassificationResult(
            doc_type=doc_type,
            language=out.get("language", "unknown"),
            confidence=float(out.get("confidence", 0.0)),
        )

    # -------------------------------------------------------------- extraction
    def extract(self, pages: list[OcrPage], schema: DocSchema) -> list[ExtractedField]:
        doc_text = "\n\n".join(
            f"--- page {p.page_number} ---\n{p.markdown}" for p in pages
        )[:120000]
        json_schema = schema.extraction_json_schema()
        out = self._chat_json(
            self.llm_model,
            [
                {"role": "system", "content": EXTRACT_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Document type: {schema.title} ({schema.jurisdiction}, "
                        f"{schema.language}). Extract all schema fields.\n\n{doc_text}"
                    ),
                },
            ],
            schema=json_schema,
        )
        fields: list[ExtractedField] = []
        for path, envelope in (out or {}).items():
            if not isinstance(envelope, dict):
                continue
            abstained = bool(envelope.get("abstained")) or envelope.get("value") is None
            span = envelope.get("text_span")
            page_no, bbox = None, None
            if span and not abstained:
                hit = find_span(pages, span)
                if hit:
                    page_no, block = hit
                    bbox = block.bbox()
            fields.append(
                ExtractedField(
                    field_path=path,
                    value=envelope.get("value"),
                    text_span=span,
                    page_number=page_no,
                    bbox=bbox,
                    confidence=float(envelope.get("confidence", 0.0)),
                    abstained=abstained,
                    method="guided_json",
                )
            )
        return fields

    # ------------------------------------------------------------------ util
    def _chat_json(self, model: str, messages: list[dict], schema: dict) -> dict[str, Any]:
        """Ask for structured JSON. Tries schema-guided decoding first; if the
        endpoint/model rejects the schema, falls back to plain json_object with
        the schema described in the prompt. Robust for a first live call."""
        for response_format in (
            {"type": "json_schema",
             "json_schema": {"name": "extraction", "schema": schema, "strict": False}},
            {"type": "json_object"},
        ):
            body: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": 0.0,
                "response_format": response_format,
            }
            if response_format["type"] == "json_object":
                body["messages"] = [
                    *messages,
                    {"role": "user",
                     "content": "Return ONLY a JSON object matching this schema:\n"
                                + json.dumps(schema)},
                ]
            resp = self._client.post("/chat/completions", json=body)
            if resp.status_code == 422 and response_format["type"] == "json_schema":
                continue  # model doesn't support json_schema — try json_object
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        raise RuntimeError("structured output failed on both json_schema and json_object")
