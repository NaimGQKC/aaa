from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.auth_service import ROLE_ORDER, ensure_access, get_current_user
from app.db import get_db
from app.models import Deal, DealMember, Document, Finding, Reconciliation, User
from app.services.ingestion import ingest_file, ingest_zip
from app.services.jobs import enqueue_deal
from app.services.oversight import oversight_stats
from app.services.pipeline import process_deal

router = APIRouter(prefix="/api/deals", tags=["deals"])


class DealCreate(BaseModel):
    name: str
    jurisdiction: list[str] = []


def _deal_view(db: Session, deal: Deal, my_role: str | None = None) -> dict:
    docs = db.execute(select(Document).where(Document.deal_id == deal.id)).scalars().all()
    findings = db.execute(select(Finding).where(Finding.deal_id == deal.id)).scalars().all()
    sev = {"high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        sev[f.severity] = sev.get(f.severity, 0) + 1
    return {
        "id": deal.id,
        "name": deal.name,
        "jurisdiction": deal.jurisdiction or [],
        "created_at": deal.created_at,
        "my_role": my_role,
        "documents": [
            {
                "id": d.id, "filename": d.filename, "doc_type": d.doc_type,
                "language": d.language, "status": d.status,
                "page_count": d.page_count,
                "classification_confidence": float(d.classification_confidence or 0),
            }
            for d in docs
        ],
        "findings_by_severity": sev,
        "oversight": oversight_stats(db, deal.id),
    }


@router.post("")
def create_deal(
    body: DealCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    deal = Deal(name=body.name, jurisdiction=body.jurisdiction)
    db.add(deal)
    db.flush()
    db.add(DealMember(deal_id=deal.id, user_id=user.id, role="owner"))
    record_event(
        db, event_type="access_granted", actor=user.email, deal_id=deal.id,
        output_ref={"user": user.email, "role": "owner", "reason": "deal created"},
    )
    db.commit()
    return _deal_view(db, deal, my_role="owner")


@router.get("")
def list_deals(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    """Deals the user is a member of, plus legacy deals with no members yet."""
    memberships = {
        m.deal_id: m.role
        for m in db.execute(
            select(DealMember).where(DealMember.user_id == user.id)
        ).scalars()
    }
    deals = db.execute(select(Deal).order_by(Deal.created_at.desc())).scalars().all()
    out = []
    for d in deals:
        if d.id in memberships:
            out.append(_deal_view(db, d, my_role=memberships[d.id]))
        else:
            has_members = db.execute(
                select(DealMember).where(DealMember.deal_id == d.id).limit(1)
            ).scalar_one_or_none()
            if has_members is None:  # legacy/orphan deal — visible, claim on open
                out.append(_deal_view(db, d, my_role=None))
    return out


@router.get("/{deal_id}")
def get_deal(
    deal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    role = ensure_access(db, user, deal_id, "viewer")
    db.commit()  # persist an orphan claim if it happened
    return _deal_view(db, db.get(Deal, deal_id), my_role=role)


@router.post("/{deal_id}/upload")
async def upload(
    deal_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Upload a single PDF or a data-room ZIP (editor+)."""
    ensure_access(db, user, deal_id, "editor")
    deal = db.get(Deal, deal_id)
    data = await file.read()
    name = file.filename or "upload"
    if name.lower().endswith(".zip"):
        docs = ingest_zip(db, deal, data, actor=user.email)
    else:
        doc, _ = ingest_file(db, deal, name, data, actor=user.email)
        docs = [doc]
    enqueue_deal(db, deal.id, [d.id for d in docs if d.status == "uploaded"])
    db.commit()
    return {"documents": [{"id": d.id, "filename": d.filename, "status": d.status} for d in docs]}


@router.post("/{deal_id}/process")
def process_now(
    deal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    ensure_access(db, user, deal_id, "editor")
    result = process_deal(db, deal_id)
    db.commit()
    return result


@router.get("/{deal_id}/reconciliations")
def reconciliations(
    deal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict]:
    ensure_access(db, user, deal_id, "viewer")
    rows = (
        db.execute(select(Reconciliation).where(Reconciliation.deal_id == deal_id))
        .scalars().all()
    )
    return [
        {
            "id": r.id, "rule_key": r.rule_key, "status": r.status,
            "severity": r.severity, "details": r.details,
        }
        for r in rows
    ]


# ---- team management (GitHub-style collaborators) ---------------------------
class MemberBody(BaseModel):
    email: str
    role: str = "viewer"

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in ROLE_ORDER:
            raise ValueError(f"role must be one of {sorted(ROLE_ORDER)}")
        return v


@router.get("/{deal_id}/members")
def list_members(
    deal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict]:
    ensure_access(db, user, deal_id, "viewer")
    rows = db.execute(
        select(DealMember, User)
        .join(User, User.id == DealMember.user_id)
        .where(DealMember.deal_id == deal_id)
    ).all()
    return [
        {"user_id": u.id, "email": u.email, "name": u.name, "role": m.role}
        for m, u in rows
    ]


@router.post("/{deal_id}/members")
def add_member(
    deal_id: str,
    body: MemberBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ensure_access(db, user, deal_id, "owner")
    target = db.execute(
        select(User).where(User.email == body.email.strip().lower())
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            404, "no account with that email — ask them to register first, then invite them"
        )
    existing = db.execute(
        select(DealMember).where(
            DealMember.deal_id == deal_id, DealMember.user_id == target.id
        )
    ).scalar_one_or_none()
    if existing:
        existing.role = body.role
    else:
        db.add(DealMember(
            deal_id=deal_id, user_id=target.id, role=body.role, invited_by=user.id
        ))
    record_event(
        db, event_type="access_granted", actor=user.email, deal_id=deal_id,
        output_ref={"user": target.email, "role": body.role},
    )
    db.commit()
    return {"user_id": target.id, "email": target.email, "name": target.name, "role": body.role}


@router.delete("/{deal_id}/members/{user_id}")
def remove_member(
    deal_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ensure_access(db, user, deal_id, "owner")
    member = db.execute(
        select(DealMember).where(
            DealMember.deal_id == deal_id, DealMember.user_id == user_id
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(404, "not a member")
    if member.role == "owner":
        owners = [
            m for m in db.execute(
                select(DealMember).where(
                    DealMember.deal_id == deal_id, DealMember.role == "owner"
                )
            ).scalars()
        ]
        if len(owners) <= 1:
            raise HTTPException(409, "cannot remove the last owner")
    target = db.get(User, user_id)
    db.delete(member)
    record_event(
        db, event_type="access_revoked", actor=user.email, deal_id=deal_id,
        output_ref={"user": target.email if target else user_id},
    )
    db.commit()
    return {"ok": True}
