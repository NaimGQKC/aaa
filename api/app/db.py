from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        if url.startswith("sqlite"):
            db_path = url.split("///", 1)[-1]
            if db_path and db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            # check_same_thread=False: shared across the API request threads and
            # the in-process worker thread. timeout + WAL + busy_timeout let a
            # concurrent writer wait instead of erroring "database is locked".
            _engine = create_engine(
                url, connect_args={"check_same_thread": False, "timeout": 30}
            )

            @event.listens_for(_engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _rec):  # noqa: ANN001
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA busy_timeout=30000")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.close()
        else:
            _engine = create_engine(url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def session_factory() -> sessionmaker:
    get_engine()
    return _SessionLocal  # type: ignore[return-value]


def get_db() -> Iterator[Session]:
    SessionLocal = session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    models.Base.metadata.create_all(get_engine())
