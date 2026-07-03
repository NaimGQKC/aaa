from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Deal, Document, Finding, Reconciliation
from app.services.ingestion import ingest_file, ingest_zip
from app.services.jobs import enqueue_deal
from app.services.pipeline import process_deal

router = APIRouter(prefix="/api/deals", tags=["deals"])


class DealCreate(BaseModel):
    name: str
    jurisdiction: list[str] = []


def _deal_view(db: Session, deal: Deal) -> dict:
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
    }


@router.post("")
def create_deal(body: DealCreate, db: Session = Depends(get_db)) -> dict:
    deal = Deal(name=body.name, jurisdiction=body.jurisdiction)
    db.add(deal)
    db.commit()
    return _deal_view(db, deal)


@router.get("")
def list_deals(db: Session = Depends(get_db)) -> list[dict]:
    deals = db.execute(select(Deal).order_by(Deal.created_at.desc())).scalars().all()
    return [_deal_view(db, d) for d in deals]


@router.get("/{deal_id}")
def get_deal(deal_id: str, db: Session = Depends(get_db)) -> dict:
    deal = db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(404, "deal not found")
    return _deal_view(db, deal)


@router.post("/{deal_id}/upload")
async def upload(deal_id: str, file: UploadFile, db: Session = Depends(get_db)) -> dict:
    """Upload a single PDF or a data-room ZIP; documents are queued for the
    pipeline (fan-out one job per file, deal finalization as fan-in)."""
    deal = db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(404, "deal not found")
    data = await file.read()
    name = file.filename or "upload"
    if name.lower().endswith(".zip"):
        docs = ingest_zip(db, deal, data)
    else:
        doc, _ = ingest_file(db, deal, name, data)
        docs = [doc]
    enqueue_deal(db, deal.id, [d.id for d in docs if d.status == "uploaded"])
    db.commit()
    return {"documents": [{"id": d.id, "filename": d.filename, "status": d.status} for d in docs]}


@router.post("/{deal_id}/process")
def process_now(deal_id: str, db: Session = Depends(get_db)) -> dict:
    """Synchronous end-to-end processing (demo/dev convenience)."""
    deal = db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(404, "deal not found")
    result = process_deal(db, deal_id)
    db.commit()
    return result


@router.get("/{deal_id}/reconciliations")
def reconciliations(deal_id: str, db: Session = Depends(get_db)) -> list[dict]:
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
