"""Shared fixtures. Each test gets its own SQLite file and a migrated schema."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.database import reset_engine
from app.db.migrate import upgrade_database
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("INGESTION_ENABLED", "false")
    get_settings.cache_clear()
    reset_engine()
    upgrade_database()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    reset_engine()
    get_settings.cache_clear()
