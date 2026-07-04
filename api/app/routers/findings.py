from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.auth_service import ensure_access, get_current_user
from app.db import get_db
from app.models import Finding, User

router = APIRouter(prefix="/api", tags=["findings"])


def _finding_view(f: Finding) -> dict:
    return {
        "id": f.id, "deal_id": f.deal_id, "document_id": f.document_id,
        "category": f.category, "severity": f.severity, "title": f.title,
        "description": f.description, "citations": f.citations or [],
        "rule_key": f.rule_key, "confidence": float(f.confidence or 0),
        "human_status": f.human_status, "human_reason": f.human_reason,
        "human_actor": f.human_actor, "created_at": f.created_at,
    }


@router.get("/deals/{deal_id}/findings")
def deal_findings(
    deal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict]:
    ensure_access(db, user, deal_id, "viewer")
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    rows = db.execute(select(Finding).where(Finding.deal_id == deal_id)).scalars().all()
    rows.sort(key=lambda f: (order.get(f.severity, 9), f.category))
    return [_finding_view(f) for f in rows]


class ReviewBody(BaseModel):
    """Human oversight event (AI Act Article 26 / Article 14 design): the
    reason is MANDATORY, and the actor is the AUTHENTICATED user — identity
    can't be typed in, it comes from the session."""

    status: str  # 'accepted' | 'overridden'
    reason: str

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in ("accepted", "overridden"):
            raise ValueError("status must be 'accepted' or 'overridden'")
        return v

    @field_validator("reason")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v.strip()


@router.post("/findings/{finding_id}/review")
def review_finding(
    finding_id: str,
    body: ReviewBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    f = db.get(Finding, finding_id)
    if f is None:
        raise HTTPException(404, "finding not found")
    ensure_access(db, user, f.deal_id, "reviewer")
    f.human_status = body.status
    f.human_reason = body.reason
    f.human_actor = user.email
    record_event(
        db,
        event_type="human_review",
        actor=user.email,
        deal_id=f.deal_id,
        document_id=f.document_id,
        input_ref={"finding_id": f.id, "title": f.title, "severity": f.severity},
        output_ref={"status": body.status, "reason": body.reason},
    )
    db.commit()
    return _finding_view(f)
