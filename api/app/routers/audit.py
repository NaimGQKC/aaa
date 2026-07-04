from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import verify_chain
from app.auth_service import ensure_access, get_current_user
from app.db import get_db
from app.models import AuditEvent, User

router = APIRouter(prefix="/api", tags=["audit"])


@router.get("/deals/{deal_id}/audit")
def deal_audit(
    deal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict]:
    ensure_access(db, user, deal_id, "viewer")
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
def audit_verify(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    """Re-walk the full hash chain — tampering with any historical event
    breaks verification from that point on (AI Act Art. 12 traceability)."""
    return verify_chain(db)
