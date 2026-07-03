"""Seed a full demo deal end-to-end using the synthetic document set:
ingest -> OCR -> classify -> extract -> reconcile -> red flags -> report.

Run from the repo root:  make seed
(zero external services needed: local provider + SQLite + local storage)
"""

from __future__ import annotations

import sys

from synthetic_docs import ALL_DOCS, build_pdf

from app.audit import verify_chain
from app.db import init_db, session_factory
from app.models import Deal, Finding
from app.services.ingestion import ingest_file
from app.services.pipeline import process_deal
from app.services.report import generate_report


def main() -> int:
    init_db()
    db = session_factory()()
    deal = Deal(name="Iberia-Occitanie Portfolio (demo)", jurisdiction=["ES", "FR"])
    db.add(deal)
    db.flush()

    for sdoc in ALL_DOCS:
        pdf = build_pdf(sdoc)
        doc, created = ingest_file(db, deal, sdoc.filename, pdf, actor="seed-script")
        print(f"  ingested {sdoc.filename} ({len(pdf)} bytes, created={created})")

    result = process_deal(db, deal.id)
    print(f"  pipeline: {result['status']} — {result.get('findings', 0)} findings, "
          f"{result.get('reconciliations', 0)} reconciliation rows")

    report = generate_report(db, deal.id, actor="seed-script")
    db.commit()

    findings = db.query(Finding).filter(Finding.deal_id == deal.id).all()
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda f: order.get(f.severity, 9))
    print(f"\nDeal {deal.id} — findings:")
    for f in findings:
        print(f"  [{f.severity.upper():6}] {f.category:28} {f.title}")

    chain = verify_chain(db)
    print(f"\naudit chain: valid={chain['valid']} events={chain['events']}")
    print(f"report: id={report.id} html={bool(report.storage_key_html)} "
          f"pdf={bool(report.storage_key_pdf)} docx={bool(report.storage_key_docx)}")
    print(f"\nOpen the UI at http://localhost:5173 (deal id {deal.id})")
    db.close()
    return 0 if chain["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
