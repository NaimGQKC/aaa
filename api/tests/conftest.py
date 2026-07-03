import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for p in (REPO / "api", REPO / "packages" / "schemas", REPO / "scripts"):
    sys.path.insert(0, str(p))


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    """Isolated settings: throwaway SQLite DB + local storage per test."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.sqlite3")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("DD_PROVIDER", "local")

    import app.config as config
    import app.db as db
    import app.storage as storage

    config.get_settings.cache_clear()
    db._engine = None
    db._SessionLocal = None
    storage._storage = None
    db.init_db()
    yield
    config.get_settings.cache_clear()
    db._engine = None
    db._SessionLocal = None
    storage._storage = None


@pytest.fixture()
def db_session(app_env):
    from app.db import session_factory

    s = session_factory()()
    yield s
    s.close()
