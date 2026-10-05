"""Tests for the foundation HTTP API."""

import logging

from app.api.routes import system as system_routes


def test_root_describes_the_service(client):
    response = client.get("/")
    body = response.json()

    assert response.status_code == 200
    assert body["service"] == "Ghana Education News"
    assert body["version"] == "0.9.0"
    assert body["environment"] == "development"
    assert body["health"] == "/health"
    assert body["docs"] == "/docs"
    assert body["reader"] == "/app/"


def test_health_reports_a_live_database(client):
    response = client.get("/health")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["service"] == "Ghana Education News"


def test_health_hides_database_failures(client, monkeypatch, caplog):
    def broken_engine():
        raise RuntimeError("password=secret-db-down")

    monkeypatch.setattr(system_routes, "get_engine", broken_engine)
    with caplog.at_level(logging.ERROR):
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable"
    assert "secret-db-down" not in response.text
    assert "Database health check failed" in caplog.text


def test_api_docs_are_available(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()
