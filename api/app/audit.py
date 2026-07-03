"""Hash-chained, append-only audit log — engineered to EU AI Act Article 12
(automatic record-keeping) and Article 26(6) (deployer log retention, 6-month
floor) even though this DD use case is very likely not Annex III high-risk.

hash = SHA-256(prev_hash || canonical(payload)); the chain makes tampering
detectable end-to-end. verify_chain() re-walks and re-hashes every event.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent

GENESIS = "0" * 64


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _ts(ev: AuditEvent) -> str | None:
    """Canonical timestamp: UTC, tz-stripped — identical whether the row is
    in-memory (tz-aware) or reloaded from SQLite (naive) / Postgres."""
    if ev.timestamp is None:
        return None
    t = ev.timestamp
    if t.tzinfo is not None:
        t = t.astimezone(timezone.utc).replace(tzinfo=None)
    return t.isoformat()


def _payload(ev: AuditEvent) -> dict[str, Any]:
    return {
        "deal_id": ev.deal_id,
        "document_id": ev.document_id,
        "event_type": ev.event_type,
        "actor": ev.actor,
        "input_ref": ev.input_ref,
        "output_ref": ev.output_ref,
        "model_version": ev.model_version,
        "prompt_version": ev.prompt_version,
        "timestamp": _ts(ev),
    }


def record_event(
    db: Session,
    *,
    event_type: str,
    actor: str,
    deal_id: str | None = None,
    document_id: str | None = None,
    input_ref: dict | None = None,
    output_ref: dict | None = None,
    model_version: str | None = None,
    prompt_version: str | None = None,
) -> AuditEvent:
    last = db.execute(
        select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)
    ).scalar_one_or_none()
    prev_hash = last.hash if last and last.hash else GENESIS

    ev = AuditEvent(
        deal_id=deal_id,
        document_id=document_id,
        event_type=event_type,
        actor=actor,
        input_ref=input_ref,
        output_ref=output_ref,
        model_version=model_version,
        prompt_version=prompt_version,
        prev_hash=prev_hash,
    )
    db.add(ev)
    db.flush()  # populate timestamp default
    ev.hash = hashlib.sha256((prev_hash + _canonical(_payload(ev))).encode()).hexdigest()
    db.flush()
    return ev


def verify_chain(db: Session) -> dict[str, Any]:
    """Re-walk the whole chain; returns {'valid': bool, 'events': n, 'broken_at': id|None}."""
    events = db.execute(select(AuditEvent).order_by(AuditEvent.id.asc())).scalars().all()
    prev = GENESIS
    for ev in events:
        if ev.prev_hash != prev:
            return {"valid": False, "events": len(events), "broken_at": ev.id}
        expected = hashlib.sha256((prev + _canonical(_payload(ev))).encode()).hexdigest()
        if ev.hash != expected:
            return {"valid": False, "events": len(events), "broken_at": ev.id}
        prev = ev.hash
    return {"valid": True, "events": len(events), "broken_at": None}
