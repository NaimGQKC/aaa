from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import verify_chain
from app.db import get_db
from app.models import AuditEvent

router = APIRouter(prefix="/api", tags=["audit"])


@router.get("/deals/{deal_id}/audit")
def deal_audit(deal_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.execute(
            select(AuditEvent).where(AuditEvent.deal_id == deal_id).order_by(AuditEvent.id)
        ).scalars().all()
    )
    return [
        {
            "id": a.id, "event_type": a.event_type, "actor": a.actor,
            "document_id": a.document_id, "input_ref": a.input_ref,
            "output_ref": a.output_ref, "model_version": a.model_version,
            "prompt_version": a.prompt_version, "timestamp": a.timestamp,
            "prev_hash": a.prev_hash, "hash": a.hash,
        }
        for a in rows
    ]


@router.get("/audit/verify")
def audit_verify(db: Session = Depends(get_db)) -> dict:
    """Re-walk the full hash chain — tampering with any historical event
    breaks verification from that point on (AI Act Art. 12 traceability)."""
    return verify_chain(db)
