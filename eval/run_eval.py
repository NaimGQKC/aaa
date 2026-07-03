"""Eval harness (spec Phase 5 / §8): per-doc-type field-level precision /
recall / F1 plus citation accuracy and abstention correctness, computed on
the synthetic gold set. CI fails when F1 drops below the per-type threshold.

Usage:  make eval
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from synthetic_docs import ALL_DOCS, SyntheticDoc, build_pdf

from app.providers.local import LocalProvider
from dd_schemas import get_schema

F1_THRESHOLD = 0.90        # spec Phase 2 acceptance: >=90% field-level accuracy
CITATION_THRESHOLD = 0.95


def norm_value(v) -> str:
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip().casefold()


def eval_doc(provider: LocalProvider, sdoc: SyntheticDoc) -> dict:
    schema = get_schema(sdoc.schema_key)
    assert schema is not None
    pages = provider.ocr(build_pdf(sdoc), sdoc.filename)

    cls = provider.classify(pages, [get_schema(d.schema_key) for d in ALL_DOCS])
    fields = provider.extract(pages, schema)
    extracted = {f.field_path: f for f in fields if not f.abstained}
    abstained = {f.field_path for f in fields if f.abstained}

    gold = {k: v for k, v in sdoc.gold.items() if not k.startswith("__")}
    expect_abstained = set(sdoc.gold.get("__expect_abstained__", []))
    gold_units = sdoc.gold.get("__units__")

    tp = fp = 0
    wrong: list[str] = []
    for path, f in extracted.items():
        if path in gold:
            if norm_value(f.value) == norm_value(gold[path]):
                tp += 1
            else:
                fp += 1
                wrong.append(f"{path}: got {f.value!r} want {gold[path]!r}")
        # extracted fields outside the gold set are not penalised (gold is a
        # subset of the schema), except fields gold says must be abstained:
        elif path in expect_abstained:
            fp += 1
            wrong.append(f"{path}: extracted but gold requires abstention")

    fn = sum(1 for path in gold if path not in extracted)
    for path in gold:
        if path not in extracted:
            wrong.append(f"{path}: MISSING (gold {gold[path]!r})")

    # units array check (rent roll): subset-match each gold unit
    if gold_units is not None:
        got_units = (extracted.get("units").value if "units" in extracted else []) or []
        for gu in gold_units:
            match = next(
                (u for u in got_units if u.get("unit_id") == gu["unit_id"]), None
            )
            ok = match is not None and all(
                norm_value(match.get(k)) == norm_value(v) for k, v in gu.items()
            )
            if ok:
                tp += 1
            else:
                fn += 1
                wrong.append(f"units[{gu['unit_id']}]: got {match!r} want {gu!r}")

    # citation accuracy: cited block must actually contain the text span,
    # and the span must exist on the cited page.
    cited = citation_ok = 0
    for f in extracted.values():
        if f.page_number is None or f.text_span is None:
            continue
        cited += 1
        page = next((p for p in pages if p.page_number == f.page_number), None)
        if page and any(f.text_span in b.content or b.content in f.text_span
                        for b in page.blocks):
            citation_ok += 1

    abstention_correct = expect_abstained.issubset(abstained)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "doc_type": sdoc.schema_key,
        "classified_as": cls.doc_type,
        "classification_ok": cls.doc_type == sdoc.schema_key,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "citation_accuracy": round(citation_ok / cited, 4) if cited else 1.0,
        "abstention_correct": abstention_correct,
        "tp": tp, "fp": fp, "fn": fn,
        "errors": wrong,
    }


def main() -> int:
    provider = LocalProvider()
    results = [eval_doc(provider, d) for d in ALL_DOCS]

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "latest.json").write_text(json.dumps(results, indent=2))

    print(f"{'doc type':24} {'class':5} {'P':>6} {'R':>6} {'F1':>6} {'cite':>6} abst")
    failed = False
    for r in results:
        print(
            f"{r['doc_type']:24} {'ok' if r['classification_ok'] else 'FAIL':5} "
            f"{r['precision']:6.2%} {r['recall']:6.2%} {r['f1']:6.2%} "
            f"{r['citation_accuracy']:6.2%} {'ok' if r['abstention_correct'] else 'FAIL'}"
        )
        for e in r["errors"]:
            print(f"    ! {e}")
        if (
            r["f1"] < F1_THRESHOLD
            or r["citation_accuracy"] < CITATION_THRESHOLD
            or not r["classification_ok"]
            or not r["abstention_correct"]
        ):
            failed = True

    if failed:
        print(f"\nEVAL FAILED (thresholds: F1>={F1_THRESHOLD}, "
              f"citation>={CITATION_THRESHOLD})")
        return 1
    print("\nEVAL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
