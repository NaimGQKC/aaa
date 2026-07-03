from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Report
from app.services.report import generate_report
from app.storage import get_storage

router = APIRouter(prefix="/api", tags=["reports"])

MEDIA = {
    "html": "text/html",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/deals/{deal_id}/report")
def create_report(deal_id: str, db: Session = Depends(get_db)) -> dict:
    report = generate_report(db, deal_id)
    db.commit()
    return {
        "id": report.id,
        "deal_id": report.deal_id,
        "formats": {
            "html": bool(report.storage_key_html),
            "pdf": bool(report.storage_key_pdf),
            "docx": bool(report.storage_key_docx),
        },
    }


@router.get("/deals/{deal_id}/reports")
def list_reports(deal_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.execute(
            select(Report).where(Report.deal_id == deal_id).order_by(Report.created_at.desc())
        ).scalars().all()
    )
    return [
        {
            "id": r.id, "created_at": r.created_at,
            "formats": {
                "html": bool(r.storage_key_html),
                "pdf": bool(r.storage_key_pdf),
                "docx": bool(r.storage_key_docx),
            },
        }
        for r in rows
    ]


@router.get("/reports/{report_id}.{ext}")
def download_report(report_id: str, ext: str, db: Session = Depends(get_db)) -> Response:
    if ext not in MEDIA:
        raise HTTPException(400, f"unsupported format {ext}")
    r = db.get(Report, report_id)
    if r is None:
        raise HTTPException(404, "report not found")
    key = {"html": r.storage_key_html, "pdf": r.storage_key_pdf, "docx": r.storage_key_docx}[ext]
    if not key:
        raise HTTPException(404, f"{ext} not generated for this report")
    return Response(content=get_storage().get(key), media_type=MEDIA[ext])
