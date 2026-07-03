"""The per-document pipeline: OCR -> classify -> extract, then deal-level
fan-in: reconcile -> red flags.

Design (spec §4.4): a DAG of idempotent stages. Each stage's completion is
recorded in stage_runs keyed by (document_id, stage, model_version,
prompt_version); re-runs with unchanged versions are skipped, a version bump
re-runs the stage. Every OCR/LLM call emits an audit event.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.config import get_settings
from app.models import Deal, Document, Extraction, Page, StageRun
from app.providers import get_provider
from app.providers.base import OcrBlock, OcrPage, Provider
from app.services.redflags import run_redflags
from app.services.reconcile import run_reconciliation
from app.storage import derived_key, get_storage
from dd_schemas import get_schema, list_schemas

log = logging.getLogger("pipeline")


def _stage_done(db: Session, document_id: str, stage: str, provider: Provider) -> bool:
    return (
        db.execute(
            select(StageRun).where(
                StageRun.document_id == document_id,
                StageRun.stage == stage,
                StageRun.model_version == provider.model_version,
                StageRun.prompt_version == provider.prompt_version,
                StageRun.status == "done",
            )
        ).scalar_one_or_none()
        is not None
    )


def _mark_stage(db: Session, document_id: str, stage: str, provider: Provider) -> None:
    db.add(
        StageRun(
            document_id=document_id,
            stage=stage,
            model_version=provider.model_version,
            prompt_version=provider.prompt_version,
            status="done",
        )
    )


def _load_pages(db: Session, document_id: str) -> list[OcrPage]:
    rows = (
        db.execute(
            select(Page).where(Page.document_id == document_id).order_by(Page.page_number)
        )
        .scalars()
        .all()
    )
    pages: list[OcrPage] = []
    for r in rows:
        blocks = [
            OcrBlock(
                type=b["type"],
                x1=b["top_left_x"], y1=b["top_left_y"],
                x2=b["bottom_right_x"], y2=b["bottom_right_y"],
                content=b["content"],
            )
            for b in (r.ocr_blocks or [])
        ]
        pages.append(
            OcrPage(
                page_number=r.page_number,
                markdown=r.ocr_markdown or "",
                blocks=blocks,
                width=r.width or 0,
                height=r.height or 0,
                dpi=r.dpi or 72,
                avg_confidence=float(r.avg_confidence or 1.0),
                min_confidence=float(r.min_confidence or 1.0),
            )
        )
    return pages


def process_document(db: Session, document_id: str) -> Document:
    """Run OCR -> classify -> extract for one document (idempotent)."""
    provider = get_provider()
    settings = get_settings()
    doc = db.get(Document, document_id)
    if doc is None:
        raise ValueError(f"document {document_id} not found")
    if doc.mime_type != "application/pdf":
        doc.status = "unsupported"
        db.flush()
        return doc

    # ---- stage: OCR --------------------------------------------------------
    if not _stage_done(db, doc.id, "ocr", provider):
        pdf_bytes = get_storage().get(doc.storage_key_original)
        pages = provider.ocr(pdf_bytes, doc.filename or "document.pdf")
        db.query(Page).filter(Page.document_id == doc.id).delete()
        for p in pages:
            blocks_json = [
                {
                    "type": b.type,
                    "top_left_x": b.x1, "top_left_y": b.y1,
                    "bottom_right_x": b.x2, "bottom_right_y": b.y2,
                    "content": b.content,
                }
                for b in p.blocks
            ]
            ocr_key = derived_key(doc.deal_id, doc.id, "ocr", f"{p.page_number}.json")
            get_storage().put(
                ocr_key,
                json.dumps({"markdown": p.markdown, "blocks": blocks_json}).encode(),
            )
            db.add(
                Page(
                    document_id=doc.id,
                    page_number=p.page_number,
                    ocr_markdown=p.markdown,
                    ocr_blocks=blocks_json,
                    width=p.width, height=p.height, dpi=p.dpi,
                    avg_confidence=p.avg_confidence,
                    min_confidence=p.min_confidence,
                )
            )
        doc.page_count = len(pages)
        doc.status = "ocr"
        record_event(
            db, event_type="ocr_run", actor=f"provider:{provider.name}",
            deal_id=doc.deal_id, document_id=doc.id,
            input_ref={"storage_key": doc.storage_key_original},
            output_ref={"pages": len(pages)},
            model_version=provider.model_version,
        )
        _mark_stage(db, doc.id, "ocr", provider)
        db.flush()

    pages = _load_pages(db, doc.id)

    # ---- stage: classify ---------------------------------------------------
    if not _stage_done(db, doc.id, "classify", provider):
        result = provider.classify(pages, list_schemas())
        doc.doc_type = result.doc_type
        doc.language = result.language
        doc.classification_confidence = result.confidence
        doc.status = "classified"
        record_event(
            db, event_type="classification", actor=f"provider:{provider.name}",
            deal_id=doc.deal_id, document_id=doc.id,
            input_ref={"pages_used": min(2, len(pages))},
            output_ref={
                "doc_type": result.doc_type,
                "language": result.language,
                "confidence": result.confidence,
            },
            model_version=provider.model_version,
            prompt_version=provider.prompt_version,
        )
        _mark_stage(db, doc.id, "classify", provider)
        db.flush()

    # ---- stage: extract ----------------------------------------------------
    schema = get_schema(doc.doc_type or "")
    if schema is None:
        # Unregistered/exotic doc: abstain entirely -> human triage queue.
        doc.status = "extracted"
        db.flush()
        return doc

    if not _stage_done(db, doc.id, "extract", provider):
        fields = provider.extract(pages, schema)
        db.query(Extraction).filter(Extraction.document_id == doc.id).delete()
        for f in fields:
            abstained = f.abstained or f.confidence < settings.abstain_below_confidence
            db.add(
                Extraction(
                    document_id=doc.id,
                    schema_key=schema.key,
                    schema_version=schema.version,
                    field_path=f.field_path,
                    value_json=None if abstained else f.value,
                    page_number=f.page_number,
                    bbox=f.bbox,
                    text_span=f.text_span,
                    confidence=f.confidence,
                    method=f.method,
                    model_version=provider.model_version,
                    prompt_version=provider.prompt_version,
                    abstained=abstained,
                )
            )
        doc.status = "extracted"
        record_event(
            db, event_type="extraction", actor=f"provider:{provider.name}",
            deal_id=doc.deal_id, document_id=doc.id,
            input_ref={"schema_key": schema.key, "schema_version": schema.version},
            output_ref={
                "fields": len(fields),
                "abstained": sum(1 for f in fields if f.abstained),
            },
            model_version=provider.model_version,
            prompt_version=provider.prompt_version,
        )
        _mark_stage(db, doc.id, "extract", provider)
        db.flush()

    return doc


def finalize_deal(db: Session, deal_id: str) -> dict:
    """Deal-level fan-in: once all documents are extracted, run cross-document
    reconciliation and the red-flag rules engine."""
    deal = db.get(Deal, deal_id)
    if deal is None:
        raise ValueError(f"deal {deal_id} not found")
    docs = db.execute(select(Document).where(Document.deal_id == deal_id)).scalars().all()
    pending = [d for d in docs if d.status in ("uploaded", "ocr", "classified")]
    if pending:
        return {"status": "waiting", "pending": [d.id for d in pending]}

    recon = run_reconciliation(db, deal)
    flags = run_redflags(db, deal)
    for d in docs:
        if d.status == "extracted":
            d.status = "reconciled"
    record_event(
        db, event_type="deal_finalized", actor="pipeline",
        deal_id=deal_id,
        output_ref={"reconciliations": recon, "findings": flags},
    )
    db.flush()
    return {"status": "done", "reconciliations": recon, "findings": flags}


def process_deal(db: Session, deal_id: str) -> dict:
    """Convenience: process every document then finalize (used by seed/eval
    and the synchronous API path)."""
    docs = db.execute(select(Document).where(Document.deal_id == deal_id)).scalars().all()
    for d in docs:
        try:
            process_document(db, d.id)
        except Exception as exc:  # dead-letter the doc, keep the deal going
            log.exception("document %s failed", d.id)
            d.status = "failed"
            d.error = str(exc)
    return finalize_deal(db, deal_id)
