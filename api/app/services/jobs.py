"""Durable job queue on Postgres/SQLite (POC stand-in for Hatchet with the
semantics the spec requires): jobs persist across restarts, retry with
exponential backoff, and dead-letter after max_attempts for human triage.

One job per document (fan-out); `finalize_deal` acts as the fan-in barrier —
it no-ops with status 'waiting' until every sibling document is extracted.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import session_factory
from app.models import Job
from app.services.pipeline import finalize_deal, process_document

log = logging.getLogger("jobs")

BACKOFF_BASE_SECONDS = 5


def enqueue(db: Session, kind: str, payload: dict) -> Job:
    job = Job(kind=kind, payload=payload)
    db.add(job)
    db.flush()
    return job


def enqueue_deal(db: Session, deal_id: str, document_ids: list[str]) -> list[Job]:
    jobs = [
        enqueue(db, "process_document", {"document_id": d, "deal_id": deal_id})
        for d in document_ids
    ]
    jobs.append(enqueue(db, "finalize_deal", {"deal_id": deal_id}))
    return jobs


def _run_job(db: Session, job: Job) -> bool:
    """Returns True when done, False to requeue (fan-in waiting)."""
    payload = job.payload or {}
    if job.kind == "process_document":
        process_document(db, payload["document_id"])
        return True
    if job.kind == "finalize_deal":
        result = finalize_deal(db, payload["deal_id"])
        return result.get("status") != "waiting"
    raise ValueError(f"unknown job kind {job.kind}")


def work_once(SessionLocal=None) -> bool:
    """Claim and run one due job. Returns True if a job was processed."""
    SessionLocal = SessionLocal or session_factory()
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        job = db.execute(
            select(Job)
            .where(Job.status == "pending", Job.run_after <= now)
            .order_by(Job.created_at)
            .limit(1)
        ).scalar_one_or_none()
        if job is None:
            return False
        job.status = "running"
        job.attempts += 1
        db.commit()
        try:
            done = _run_job(db, job)
            if done:
                job.status = "done"
            else:  # fan-in barrier not met yet — requeue shortly
                job.status = "pending"
                job.attempts -= 1
                job.run_after = datetime.now(timezone.utc) + timedelta(seconds=2)
            db.commit()
        except Exception as exc:
            db.rollback()
            job = db.get(Job, job.id)
            job.last_error = str(exc)[:2000]
            if job.attempts >= job.max_attempts:
                job.status = "dead"  # dead-letter -> human triage
                log.error("job %s dead-lettered: %s", job.id, exc)
            else:
                job.status = "pending"
                job.run_after = datetime.now(timezone.utc) + timedelta(
                    seconds=BACKOFF_BASE_SECONDS * (2 ** (job.attempts - 1))
                )
                log.warning("job %s failed (attempt %s): %s", job.id, job.attempts, exc)
            db.commit()
        return True
    finally:
        db.close()


class WorkerThread(threading.Thread):
    """In-process polling worker (started from the API lifespan). Runs the
    same work_once() loop as the standalone `workers/worker.py` process."""

    def __init__(self, poll_seconds: float = 1.0) -> None:
        super().__init__(daemon=True, name="dd-worker")
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()

    def run(self) -> None:
        log.info("worker thread started")
        while not self._stop.is_set():
            try:
                if not work_once():
                    time.sleep(self.poll_seconds)
            except Exception:
                log.exception("worker loop error")
                time.sleep(self.poll_seconds)

    def stop(self) -> None:
        self._stop.set()
