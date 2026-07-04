from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_service import ensure_access, get_current_user
from app.db import get_db
from app.models import Document, Extraction, Page, User
from app.storage import get_storage

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _load_doc(db: Session, user: User, document_id: str) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "document not found")
    ensure_access(db, user, doc.deal_id, "viewer")
    return doc


@router.get("/{document_id}")
def get_document(
    document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    doc = _load_doc(db, user, document_id)
    return {
        "id": doc.id, "deal_id": doc.deal_id, "filename": doc.filename,
        "doc_type": doc.doc_type, "language": doc.language, "status": doc.status,
        "page_count": doc.page_count, "sha256": doc.sha256,
        "classification_confidence": float(doc.classification_confidence or 0),
    }


@router.get("/{document_id}/pdf")
def get_pdf(
    document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Response:
    doc = _load_doc(db, user, document_id)
    if not doc.storage_key_original:
        raise HTTPException(404, "document not found")
    data = get_storage().get(doc.storage_key_original)
    return Response(
        content=data, media_type=doc.mime_type or "application/pdf",
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )


@router.get("/{document_id}/pages")
def get_pages(
    document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict]:
    _load_doc(db, user, document_id)
    rows = (
        db.execute(
            select(Page).where(Page.document_id == document_id).order_by(Page.page_number)
        ).scalars().all()
    )
    return [
        {
            "page_number": p.page_number, "width": p.width, "height": p.height,
            "dpi": p.dpi, "markdown": p.ocr_markdown, "blocks": p.ocr_blocks,
            "avg_confidence": float(p.avg_confidence or 0),
        }
        for p in rows
    ]


@router.get("/{document_id}/extractions")
def get_extractions(
    document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict]:
    _load_doc(db, user, document_id)
    rows = (
        db.execute(
            select(Extraction)
            .where(Extraction.document_id == document_id)
            .order_by(Extraction.field_path)
        ).scalars().all()
    )
    return [
        {
            "id": e.id, "field_path": e.field_path, "value": e.value_json,
            "text_span": e.text_span, "page": e.page_number, "bbox": e.bbox,
            "confidence": float(e.confidence or 0), "abstained": e.abstained,
            "method": e.method, "schema_key": e.schema_key,
            "schema_version": e.schema_version, "model_version": e.model_version,
        }
        for e in rows
    ]
