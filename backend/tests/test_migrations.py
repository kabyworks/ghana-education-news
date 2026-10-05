"""Tests for the migration chain."""

from sqlalchemy import inspect, text

from app.db.database import get_engine


def test_upgrade_applies_the_latest_revision(client):
    engine = get_engine()
    tables = inspect(engine).get_table_names()
    assert "alembic_version" in tables
    assert "sources" in tables

    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert version == "0007_review"
    assert "articles" in tables
    assert "stories" in tables
    assert client.get("/health").status_code == 200
