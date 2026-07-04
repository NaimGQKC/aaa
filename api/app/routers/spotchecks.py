from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Extraction, SpotCheck
from app.services.oversight import decide, ensure_sample, oversight_stats

router = APIRouter(prefix="/api", tags=["oversight"])


def _view(db: Session, c: SpotCheck) -> dict:
    ex = db.get(Extraction, c.extraction_id)
    return {
        "id": c.id,
        "deal_id": c.deal_id,
        "document_id": c.document_id,
        "extraction_id": c.extraction_id,
        "field_path": c.field_path,
        "value": ex.value_json if ex else None,
        "text_span": ex.text_span if ex else None,
        "page": ex.page_number if ex else None,
        "bbox": ex.bbox if ex else None,
        "confidence": float(ex.confidence or 0) if ex else 0,
        "status": c.status,
        "actor": c.actor,
        "reason": c.reason,
    }


@router.get("/deals/{deal_id}/spotchecks")
def deal_spotchecks(deal_id: str, db: Session = Depends(get_db)) -> list[dict]:
    checks = ensure_sample(db, deal_id)
    db.commit()
    return [_view(db, c) for c in checks]


@router.get("/deals/{deal_id}/oversight")
def deal_oversight(deal_id: str, db: Session = Depends(get_db)) -> dict:
    return oversight_stats(db, deal_id)


class SpotCheckBody(BaseModel):
    status: str  # 'match' | 'mismatch'
    actor: str
    reason: str | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in ("match", "mismatch"):
            raise ValueError("status must be 'match' or 'mismatch'")
        return v

    @field_validator("actor")
    @classmethod
    def _actor(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("actor is required")
        return v.strip()


@router.post("/spotchecks/{check_id}")
def submit_spotcheck(check_id: str, body: SpotCheckBody, db: Session = Depends(get_db)) -> dict:
    check = db.get(SpotCheck, check_id)
    if check is None:
        raise HTTPException(404, "spot check not found")
    if body.status == "mismatch" and not (body.reason or "").strip():
        raise HTTPException(422, "a reason is required when reporting a mismatch")
    decide(db, check, status=body.status, actor=body.actor, reason=body.reason)
    db.commit()
    return _view(db, check)
