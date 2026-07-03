"""ORM model — mirrors the DDL in the technical spec (§4.1).

Portability note: UUIDs are stored as 36-char strings and jsonb as JSON so the
same model runs on Postgres (compose/Supabase/Scaleway) and SQLite (zero-infra
dev + CI). On Postgres, SQLAlchemy maps JSON to jsonb-compatible storage.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[list | None] = mapped_column(JSON, default=list)  # ['ES','FR']
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), index=True)
    filename: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    mime_type: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    storage_key_original: Mapped[str | None] = mapped_column(Text)
    doc_type: Mapped[str | None] = mapped_column(Text, index=True)
    language: Mapped[str | None] = mapped_column(String(8))
    classification_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    status: Mapped[str] = mapped_column(
        Text, default="uploaded"
    )  # uploaded|ocr|classified|extracted|reconciled|reviewed|failed
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    storage_key_image: Mapped[str | None] = mapped_column(Text)
    ocr_markdown: Mapped[str | None] = mapped_column(Text)
    ocr_blocks: Mapped[list | None] = mapped_column(JSON)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    dpi: Mapped[int | None] = mapped_column(Integer)
    avg_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    min_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    schema_key: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[str | None] = mapped_column(Text)
    field_path: Mapped[str] = mapped_column(Text)
    value_json: Mapped[dict | list | str | int | float | None] = mapped_column(JSON)
    page_number: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[dict | None] = mapped_column(JSON)  # {x1,y1,x2,y2} page coords
    text_span: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    method: Mapped[str | None] = mapped_column(Text)  # 'guided_json'|'label_anchor'
    model_version: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    abstained: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), index=True)
    rule_key: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)  # 'match'|'mismatch'|'missing'
    details: Mapped[dict | None] = mapped_column(JSON)
    severity: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    category: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)  # 'high'|'medium'|'low'|'info'
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON)  # [{document_id,page,bbox,text_span}]
    rule_key: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    human_status: Mapped[str] = mapped_column(Text, default="pending")  # pending|accepted|overridden
    human_reason: Mapped[str | None] = mapped_column(Text)
    human_actor: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[str | None] = mapped_column(String(36), index=True)
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(Text)
    actor: Mapped[str | None] = mapped_column(Text)
    input_ref: Mapped[dict | None] = mapped_column(JSON)
    output_ref: Mapped[dict | None] = mapped_column(JSON)
    model_version: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str | None] = mapped_column(String(64))


class StageRun(Base):
    """Idempotency ledger: one row per (document, stage, model, prompt) run.

    This is what makes the pipeline a DAG of idempotent stages — re-runs with
    unchanged versions are skipped; a version bump re-runs the stage.
    """

    __tablename__ = "stage_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    stage: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(Text, default="")
    prompt_version: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="done")  # done|failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    """Durable job queue (Postgres/SQLite-backed). POC replacement for
    Hatchet with the same semantics the spec needs: jobs survive restarts,
    are retried with backoff, and dead-letter after max attempts. Swap-in
    point for Hatchet/Temporal when scale demands it."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(Text)  # 'process_document' | 'finalize_deal'
    payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(Text, default="pending")  # pending|running|done|failed|dead
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), index=True)
    storage_key_html: Mapped[str | None] = mapped_column(Text)
    storage_key_pdf: Mapped[str | None] = mapped_column(Text)
    storage_key_docx: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
