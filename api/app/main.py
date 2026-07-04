import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.routers import audit, auth, deals, documents, findings, reports, spotchecks
from app.services.jobs import WorkerThread

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    worker = WorkerThread()
    worker.start()
    yield
    worker.stop()


app = FastAPI(
    title="EU-Sovereign Real-Estate DD Pipeline",
    description=(
        "Agentic due-diligence pipeline for cross-border (ES-FR) real-estate "
        "transactions: EU-sovereign OCR + cited extraction + reconciliation + "
        "red-flag rules + audit-ready reporting (AI Act Art. 12/26 logging)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(deals.router)
app.include_router(documents.router)
app.include_router(findings.router)
app.include_router(reports.router)
app.include_router(spotchecks.router)
app.include_router(audit.router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": settings.dd_provider,
        "storage": settings.storage_backend,
    }
