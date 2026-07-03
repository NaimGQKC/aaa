"""Audit log: hash chain integrity + tamper detection (AI Act Art. 12)."""


def test_chain_records_and_verifies(db_session):
    from app.audit import record_event, verify_chain

    for i in range(5):
        record_event(
            db_session, event_type="llm_call", actor="test",
            deal_id="deal-1", input_ref={"i": i}, output_ref={"ok": True},
            model_version="m1", prompt_version="p1",
        )
    db_session.commit()
    result = verify_chain(db_session)
    assert result["valid"] is True
    assert result["events"] == 5


def test_tampering_is_detected(db_session):
    from app.audit import record_event, verify_chain
    from app.models import AuditEvent

    for i in range(3):
        record_event(db_session, event_type="ocr_run", actor="test", input_ref={"i": i})
    db_session.commit()

    ev = db_session.query(AuditEvent).filter(AuditEvent.id == 2).one()
    ev.input_ref = {"i": 999}  # tamper with a historical event
    db_session.commit()

    result = verify_chain(db_session)
    assert result["valid"] is False
    assert result["broken_at"] == 2


def test_chain_survives_reload(db_session):
    """Hashes must verify identically after a round-trip through the DB
    (tz-aware vs naive timestamp canonicalisation)."""
    from app.audit import record_event, verify_chain
    from app.db import session_factory

    record_event(db_session, event_type="export", actor="test")
    db_session.commit()
    db_session.close()

    fresh = session_factory()()
    try:
        assert verify_chain(fresh)["valid"] is True
    finally:
        fresh.close()
