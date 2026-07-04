"""End-to-end: synthetic deal through ingestion -> pipeline -> reconciliation
-> red flags -> report, plus the API surface (upload, review with mandatory
reason, audit verify)."""

import pytest


@pytest.fixture()
def seeded_deal(db_session):
    from synthetic_docs import ALL_DOCS, build_pdf

    from app.models import Deal
    from app.services.ingestion import ingest_file
    from app.services.pipeline import process_deal

    deal = Deal(name="test deal", jurisdiction=["ES", "FR"])
    db_session.add(deal)
    db_session.flush()
    for sdoc in ALL_DOCS:
        ingest_file(db_session, deal, sdoc.filename, build_pdf(sdoc))
    result = process_deal(db_session, deal.id)
    db_session.commit()
    assert result["status"] == "done"
    return deal


def _categories(db, deal_id):
    from app.models import Finding

    return {f.category for f in db.query(Finding).filter(Finding.deal_id == deal_id)}


def test_expected_findings(db_session, seeded_deal):
    cats = _categories(db_session, seeded_deal.id)
    # every intentionally-seeded defect must be caught:
    assert {"rent_mismatch", "title_charge", "invalid_index",
            "stale_title_extract", "deposit_below_statutory",
            "charge_inventory_missing", "epc_trajectory", "epbd_meps",
            "arrears", "vacancy", "lease_break"} <= cats
    # and the cross-jurisdiction false positives must NOT appear:
    assert "title_mismatch" not in cats
    assert "surface_mismatch" not in cats


def test_classification_and_dedup(db_session, seeded_deal):
    from synthetic_docs import ALL_DOCS, build_pdf

    from app.models import Document
    from app.services.ingestion import ingest_file

    docs = db_session.query(Document).filter(Document.deal_id == seeded_deal.id).all()
    assert {d.doc_type for d in docs} == {
        "nota_simple_es", "lease_es", "bail_commercial_fr", "rent_roll"}
    # re-ingesting the same bytes must dedup on SHA-256:
    doc, created = ingest_file(
        db_session, seeded_deal, "copy.pdf", build_pdf(ALL_DOCS[0]))
    assert created is False


def test_every_finding_with_citation_resolves(db_session, seeded_deal):
    from app.models import Finding, Page

    findings = db_session.query(Finding).filter(Finding.deal_id == seeded_deal.id).all()
    cited = [f for f in findings if f.citations]
    assert cited, "at least some findings must carry citations"
    for f in cited:
        for c in f.citations:
            assert c.get("document_id")
            if c.get("page") and c.get("text_span"):
                page = (
                    db_session.query(Page)
                    .filter(Page.document_id == c["document_id"],
                            Page.page_number == c["page"])
                    .one()
                )
                blocks_text = " ".join(b["content"] for b in page.ocr_blocks)
                assert c["text_span"] in blocks_text


def test_report_and_audit(db_session, seeded_deal):
    from app.audit import verify_chain
    from app.services.report import generate_report
    from app.storage import get_storage

    report = generate_report(db_session, seeded_deal.id)
    db_session.commit()
    html = get_storage().get(report.storage_key_html).decode()
    assert "Due Diligence Report" in html
    assert "Indexation clause references ICC" in html
    assert verify_chain(db_session)["valid"] is True


def test_review_requires_reason_and_binds_identity(app_env):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        # unauthenticated -> everything is locked
        assert client.get("/api/deals").status_code == 401

        reg = client.post("/api/auth/register", json={
            "email": "ana@fund.example", "name": "Ana", "password": "s3cret-pass"})
        assert reg.status_code == 200

        r = client.post("/api/deals", json={"name": "d1", "jurisdiction": ["ES"]})
        assert r.status_code == 200
        assert r.json()["my_role"] == "owner"

        from synthetic_docs import NOTA_SIMPLE, build_pdf

        deal_id = r.json()["id"]
        up = client.post(
            f"/api/deals/{deal_id}/upload",
            files={"file": ("nota.pdf", build_pdf(NOTA_SIMPLE), "application/pdf")},
        )
        assert up.status_code == 200
        client.post(f"/api/deals/{deal_id}/process")

        findings = client.get(f"/api/deals/{deal_id}/findings").json()
        assert findings
        fid = findings[0]["id"]

        # missing reason -> rejected (mandatory human-oversight rationale)
        bad = client.post(f"/api/findings/{fid}/review",
                          json={"status": "overridden", "reason": ""})
        assert bad.status_code == 422

        good = client.post(
            f"/api/findings/{fid}/review",
            json={"status": "overridden", "reason": "verified against registry"},
        )
        assert good.status_code == 200
        assert good.json()["human_status"] == "overridden"
        # identity comes from the session, never from the request body
        assert good.json()["human_actor"] == "ana@fund.example"

        chain = client.get("/api/audit/verify").json()
        assert chain["valid"] is True
