"""Tests for environment configuration."""

import pytest

from app.core.config import get_settings, resolve_database_url


def test_settings_use_defaults_without_env_file(monkeypatch):
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_name == "Ghana Education News"
    assert settings.app_env == "development"
    assert settings.database_url == "sqlite:///./data/ghanaed.db"
    assert settings.log_level == "INFO"
    get_settings.cache_clear()


def test_settings_read_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    get_settings.cache_clear()
    assert get_settings().database_url == "sqlite:///:memory:"
    get_settings.cache_clear()


def test_invalid_log_level_is_rejected(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "loud")
    get_settings.cache_clear()
    with pytest.raises(ValueError):
        get_settings()
    get_settings.cache_clear()


def test_relative_sqlite_url_is_placed_under_backend(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resolved = resolve_database_url("sqlite:///./data/ghanaed.db")
    assert resolved.endswith("/data/ghanaed.db")
    assert "/backend/data/ghanaed.db" in resolved.replace("\\", "/")


def test_absolute_sqlite_url_creates_parent_directory(tmp_path):
    database_file = tmp_path / "nested" / "app.db"
    resolved = resolve_database_url(f"sqlite:///{database_file.as_posix()}")
    resolved_path = resolved.removeprefix("sqlite:///")
    assert resolved_path.replace("\\", "/").endswith("nested/app.db")
    assert database_file.parent.is_dir()


def test_non_sqlite_url_is_unchanged():
    url = "postgresql+psycopg://ghanaed:secret@localhost:5432/ghanaed"
    assert resolve_database_url(url) == url
