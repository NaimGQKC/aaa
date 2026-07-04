"""Proof-of-Oversight service: spot-check sampling + review/oversight stats.

Design (anti-automation-bias):
- Spot-checks sample HIGH-confidence, non-abstained extractions — exactly the
  answers a complacent reviewer would never re-check.
- Sampling is deterministic (SHA-256 of deal+extraction ids), so re-loading a
  deal never reshuffles the queue.
- A mismatch immediately becomes a high-severity finding, so a failed check
  can't be silently ignored — and every decision writes an audit event.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.models import Document, Extraction, Finding, SpotCheck

SAMPLE_SIZE = 5
MIN_CONFIDENCE = 0.85  # only sample answers the system is confident about
# skip container fields whose values are long JSON blobs — poor 10-second checks
_SKIP_FIELDS = {"units", "titularidad", "cargas", "notas_marginales"}


def ensure_sample(db: Session, deal_id: str) -> list[SpotCheck]:
    """Return the deal's spot-check queue, creating it (deterministically)
    on first access. Items whose extraction was rebuilt are re-linked by
    field path, or dropped if the field no longer exists."""
    checks = list(
        db.execute(select(SpotCheck).where(SpotCheck.deal_id == deal_id)).scalars()
    )
    live_ids = set(
        db.execute(
            select(Extraction.id)
            .join(Document, Document.id == Extraction.document_id)
            .where(Document.deal_id == deal_id)
        ).scalars()
    )
    if checks:
        for c in checks:
            if c.extraction_id not in live_ids:
                fresh = db.execute(
                    select(Extraction).where(
                        Extraction.document_id == c.document_id,
                        Extraction.field_path == c.field_path,
                        Extraction.abstained == False,  # noqa: E712
                    )
                ).scalar_one_or_none()
                if fresh is not None:
                    c.extraction_id = fresh.id
        db.flush()
        return checks

    candidates = (
        db.execute(
            select(Extraction)
            .join(Document, Document.id == Extraction.document_id)
            .where(
                Document.deal_id == deal_id,
                Extraction.abstained == False,  # noqa: E712
                Extraction.confidence >= MIN_CONFIDENCE,
                Extraction.page_number.isnot(None),
            )
        )
        .scalars()
        .all()
    )
    candidates = [c for c in candidates if c.field_path not in _SKIP_FIELDS]
    if not candidates:
        return []

    # Deterministic shuffle, then round-robin across documents for spread.
    def key(e: Extraction) -> str:
        return hashlib.sha256(f"{deal_id}:{e.document_id}:{e.field_path}".encode()).hexdigest()

    by_doc: dict[str, list[Extraction]] = {}
    for e in sorted(candidates, key=key):
        by_doc.setdefault(e.document_id, []).append(e)
    picked: list[Extraction] = []
    while len(picked) < SAMPLE_SIZE and any(by_doc.values()):
        for doc_id in sorted(by_doc):
            if by_doc[doc_id] and len(picked) < SAMPLE_SIZE:
                picked.append(by_doc[doc_id].pop(0))

    created = [
        SpotCheck(
            deal_id=deal_id,
            document_id=e.document_id,
            extraction_id=e.id,
            field_path=e.field_path,
        )
        for e in picked
    ]
    db.add_all(created)
    record_event(
        db, event_type="spot_check_sampled", actor="oversight-service",
        deal_id=deal_id,
        output_ref={"sampled": [c.field_path for c in created],
                    "min_confidence": MIN_CONFIDENCE},
    )
    db.flush()
    return created


def decide(
    db: Session, check: SpotCheck, *, status: str, actor: str, reason: str | None
) -> SpotCheck:
    check.status = status
    check.actor = actor
    check.reason = reason
    check.decided_at = datetime.now(timezone.utc)
    if status == "mismatch":
        ex = db.get(Extraction, check.extraction_id)
        db.add(Finding(
            deal_id=check.deal_id,
            document_id=check.document_id,
            category="spot_check_mismatch",
            severity="high",
            title=f"Spot-check failed: {check.field_path}",
            description=(
                f"A human reviewer found the extracted value for "
                f"'{check.field_path}' does not match the cited source"
                + (f" — {reason}" if reason else "")
                + ". Re-verify every use of this field before relying on it."
            ),
            citations=[{
                "document_id": check.document_id,
                "page": ex.page_number if ex else None,
                "bbox": ex.bbox if ex else None,
                "text_span": ex.text_span if ex else None,
                "field_path": check.field_path,
            }],
            rule_key="spot_check",
            confidence=1.0,
        ))
    record_event(
        db, event_type="spot_check", actor=actor,
        deal_id=check.deal_id, document_id=check.document_id,
        input_ref={"spot_check_id": check.id, "field_path": check.field_path},
        output_ref={"status": status, "reason": reason},
    )
    db.flush()
    return check


def oversight_stats(db: Session, deal_id: str) -> dict:
    """Review-debt + spot-check agreement for the deal — the numbers that
    drive the oversight header, the DRAFT stamp and the report annex."""
    findings = db.execute(select(Finding).where(Finding.deal_id == deal_id)).scalars().all()
    pending = [f for f in findings if f.human_status == "pending"]
    checks = db.execute(select(SpotCheck).where(SpotCheck.deal_id == deal_id)).scalars().all()
    decided = [c for c in checks if c.status != "pending"]
    reviewers = sorted({
        a for a in (
            [f.human_actor for f in findings if f.human_actor]
            + [c.actor for c in checks if c.actor]
        )
    })
    return {
        "findings_total": len(findings),
        "findings_reviewed": len(findings) - len(pending),
        "pending_high": sum(1 for f in pending if f.severity == "high"),
        "pending": len(pending),
        "spot_checks_total": len(checks),
        "spot_checks_done": len(decided),
        "spot_checks_matched": sum(1 for c in decided if c.status == "match"),
        "reviewers": reviewers,
        "is_draft": len(pending) > 0 or (len(checks) > 0 and not decided),
    }
