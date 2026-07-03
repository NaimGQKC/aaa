"""Ingestion: upload / data-room ZIP -> dedup (SHA-256) -> MIME sniff ->
object storage + documents rows + audit events."""

from __future__ import annotations

import hashlib
import io
import zipfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.models import Deal, Document
from app.storage import get_storage, original_key

MAGIC = {
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/zip",
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}

SUPPORTED_MIME = {"application/pdf"}


def sniff_mime(data: bytes, filename: str) -> str:
    for magic, mime in MAGIC.items():
        if data[: len(magic)] == magic:
            if mime == "application/zip" and filename.lower().endswith((".docx", ".xlsx", ".pptx")):
                return "application/vnd.openxmlformats-officedocument"
            return mime
    if filename.lower().endswith(".pdf"):
        return "application/pdf"
    return "application/octet-stream"


def ingest_file(
    db: Session, deal: Deal, filename: str, data: bytes, actor: str = "ingestion-service"
) -> tuple[Document, bool]:
    """Store one file; returns (document, created). Dedup by SHA-256 within the deal."""
    sha = hashlib.sha256(data).hexdigest()
    existing = db.execute(
        select(Document).where(Document.deal_id == deal.id, Document.sha256 == sha)
    ).scalar_one_or_none()
    if existing:
        return existing, False

    mime = sniff_mime(data, filename)
    doc = Document(
        deal_id=deal.id,
        filename=filename,
        sha256=sha,
        mime_type=mime,
        status="uploaded" if mime in SUPPORTED_MIME else "unsupported",
    )
    db.add(doc)
    db.flush()
    key = original_key(deal.id, doc.id, filename)
    get_storage().put(key, data)
    doc.storage_key_original = key
    record_event(
        db,
        event_type="ingest",
        actor=actor,
        deal_id=deal.id,
        document_id=doc.id,
        input_ref={"filename": filename, "sha256": sha, "bytes": len(data)},
        output_ref={"storage_key": key, "mime": mime},
    )
    return doc, True


def ingest_zip(
    db: Session, deal: Deal, zip_bytes: bytes, actor: str = "ingestion-service"
) -> list[Document]:
    """Fan a data-room ZIP out into individual documents."""
    docs: list[Document] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir() or info.filename.startswith("__MACOSX"):
                continue
            name = info.filename.rsplit("/", 1)[-1]
            if not name or name.startswith("."):
                continue
            doc, _created = ingest_file(db, deal, name, zf.read(info), actor=actor)
            docs.append(doc)
    return docs
