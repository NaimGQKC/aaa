import re

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_service import ensure_access, get_current_user
from app.db import get_db
from app.models import Deal, Report, User
from app.services.report import generate_report
from app.storage import get_storage


def _download_name(deal_name: str | None, created_at, ext: str) -> str:
    """Human-friendly, timestamped filename e.g. DD-Report_New-deal_20260704-0012.pdf"""
    safe = re.sub(r"[^A-Za-z0-9]+", "-", (deal_name or "deal")).strip("-") or "deal"
    stamp = created_at.strftime("%Y%m%d-%H%M") if created_at else "report"
    return f"DD-Report_{safe}_{stamp}.{ext}"

router = APIRouter(prefix="/api", tags=["reports"])

MEDIA = {
    "html": "text/html",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/deals/{deal_id}/report")
def create_report(
    deal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    ensure_access(db, user, deal_id, "reviewer")
    report = generate_report(db, deal_id, actor=user.email)
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
def list_reports(
    deal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict]:
    ensure_access(db, user, deal_id, "viewer")
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
def download_report(
    report_id: str, ext: str,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> Response:
    if ext not in MEDIA:
        raise HTTPException(400, f"unsupported format {ext}")
    r = db.get(Report, report_id)
    if r is None:
        raise HTTPException(404, "report not found")
    ensure_access(db, user, r.deal_id, "viewer")
    key = {"html": r.storage_key_html, "pdf": r.storage_key_pdf, "docx": r.storage_key_docx}[ext]
    if not key:
        raise HTTPException(404, f"{ext} not generated for this report")
    deal = db.get(Deal, r.deal_id)
    filename = _download_name(deal.name if deal else None, r.created_at, ext)
    # HTML previews inline; PDF/DOCX download with the friendly name.
    disposition = "inline" if ext == "html" else "attachment"
    return Response(
        content=get_storage().get(key),
        media_type=MEDIA[ext],
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )
