"""Proof-of-Oversight: spot-check sampling, mismatch escalation, DRAFT stamp."""

import pytest


@pytest.fixture()
def seeded(db_session):
    from synthetic_docs import ALL_DOCS, build_pdf

    from app.models import Deal
    from app.services.ingestion import ingest_file
    from app.services.pipeline import process_deal

    deal = Deal(name="oversight test", jurisdiction=["ES", "FR"])
    db_session.add(deal)
    db_session.flush()
    for sdoc in ALL_DOCS:
        ingest_file(db_session, deal, sdoc.filename, build_pdf(sdoc))
    process_deal(db_session, deal.id)
    db_session.commit()
    return deal


def test_sample_is_deterministic_and_high_confidence(db_session, seeded):
    from app.models import Extraction
    from app.services.oversight import MIN_CONFIDENCE, SAMPLE_SIZE, ensure_sample

    first = ensure_sample(db_session, seeded.id)
    db_session.commit()
    assert 0 < len(first) <= SAMPLE_SIZE
    for c in first:
        ex = db_session.get(Extraction, c.extraction_id)
        assert not ex.abstained
        assert float(ex.confidence) >= MIN_CONFIDENCE

    # second call returns the same queue, not a reshuffle
    second = ensure_sample(db_session, seeded.id)
    assert [c.id for c in first] == [c.id for c in second]


def test_mismatch_escalates_to_high_finding_and_audits(db_session, seeded):
    from app.audit import verify_chain
    from app.models import Finding
    from app.services.oversight import decide, ensure_sample

    checks = ensure_sample(db_session, seeded.id)
    decide(db_session, checks[0], status="mismatch", actor="ana",
           reason="value differs from the deed")
    db_session.commit()

    escalated = (
        db_session.query(Finding)
        .filter(Finding.deal_id == seeded.id, Finding.category == "spot_check_mismatch")
        .all()
    )
    assert len(escalated) == 1
    assert escalated[0].severity == "high"
    assert verify_chain(db_session)["valid"] is True


def test_report_is_draft_until_oversight_complete(db_session, seeded):
    from app.models import Finding
    from app.services.oversight import decide, ensure_sample, oversight_stats
    from app.services.report import generate_report
    from app.storage import get_storage

    # untouched deal -> DRAFT
    r1 = generate_report(db_session, seeded.id)
    db_session.commit()
    html1 = get_storage().get(r1.storage_key_html).decode()
    assert "DRAFT" in html1

    # adjudicate every finding + decide every spot-check -> HUMAN-REVIEWED
    for f in db_session.query(Finding).filter(Finding.deal_id == seeded.id):
        f.human_status = "accepted"
        f.human_reason = "verified"
        f.human_actor = "ana"
    for c in ensure_sample(db_session, seeded.id):
        if c.status == "pending":
            decide(db_session, c, status="match", actor="ana", reason=None)
    db_session.commit()

    stats = oversight_stats(db_session, seeded.id)
    assert stats["is_draft"] is False
    r2 = generate_report(db_session, seeded.id)
    db_session.commit()
    html2 = get_storage().get(r2.storage_key_html).decode()
    assert "HUMAN-REVIEWED" in html2
