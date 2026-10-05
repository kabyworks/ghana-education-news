"""Tests for the source registry."""

from sqlalchemy.orm import Session

from app.db.database import get_engine
from app.services.source_service import record_source_check, seed_sources
from app.sources.catalog import initial_sources

CONFIRMED_RSS = {
    "https://www.myjoyonline.com/feed/",
    "https://www.adomonline.com/category/education/feed/",
    "https://3news.com/feed/",
    "https://gtec.edu.gh/feed/",
}


def rss_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Test Publisher",
        "base_url": "https://example.com/",
        "feed_url": "https://example.com/feed/",
        "source_type": "news",
        "trust_score": 0.5,
        "crawl_frequency_minutes": 180,
        "discovery_method": "rss",
    }
    payload.update(overrides)
    return payload


def test_catalog_keeps_only_checked_feed_addresses():
    sources = initial_sources()
    feeds = {item.feed_url for item in sources if item.discovery_method == "rss"}
    assert feeds == CONFIRMED_RSS
    assert all(item.feed_url is None for item in sources if item.discovery_method != "rss")


def test_create_and_read_source(client):
    created = client.post("/sources", json=rss_payload())
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Test Publisher"
    assert body["active"] is True
    assert body["parser_key"] == "generic_rss"
    assert body["last_checked_at"] is None
    assert body["last_error"] is None

    fetched = client.get(f"/sources/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["feed_url"] == "https://example.com/feed/"


def test_client_cannot_set_health_fields(client):
    created = client.post("/sources", json=rss_payload(name="Health Lock", last_error="hacked"))
    assert created.status_code == 201
    assert created.json()["last_error"] is None
    assert created.json()["last_success_at"] is None


def test_source_can_be_disabled_without_code_change(client):
    created = client.post("/sources", json=rss_payload(name="Disable Me"))
    source_id = created.json()["id"]

    disabled = client.patch(f"/sources/{source_id}", json={"active": False})
    assert disabled.status_code == 200
    assert disabled.json()["active"] is False

    active = client.get("/sources", params={"active": True})
    inactive = client.get("/sources", params={"active": False})
    assert all(item["id"] != source_id for item in active.json())
    assert any(item["id"] == source_id for item in inactive.json())

    enabled = client.patch(f"/sources/{source_id}", json={"active": True})
    assert enabled.json()["active"] is True
    assert any(item["id"] == source_id for item in client.get("/sources", params={"active": True}).json())


def test_update_and_delete_source(client):
    created = client.post("/sources", json=rss_payload(name="Temporary Desk"))
    source_id = created.json()["id"]

    updated = client.patch(
        f"/sources/{source_id}",
        json={"trust_score": 0.4, "crawl_frequency_minutes": 360},
    )
    assert updated.status_code == 200
    assert updated.json()["trust_score"] == 0.4
    assert updated.json()["crawl_frequency_minutes"] == 360

    deleted = client.delete(f"/sources/{source_id}")
    assert deleted.status_code == 204
    assert client.get(f"/sources/{source_id}").status_code == 404


def test_duplicate_name_is_rejected(client):
    assert client.post("/sources", json=rss_payload(name="Same Name")).status_code == 201
    duplicate = client.post(
        "/sources",
        json=rss_payload(name="Same Name", feed_url="https://example.com/other.xml"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "A source with this name already exists"


def test_invalid_source_input_is_rejected(client):
    missing_feed = client.post("/sources", json=rss_payload(feed_url=None))
    assert missing_feed.status_code == 422

    bad_url = client.post("/sources", json=rss_payload(name="Bad URL", base_url="javascript:alert(1)"))
    assert bad_url.status_code == 422

    with_password = client.post(
        "/sources",
        json=rss_payload(name="Secret URL", feed_url="https://user:password@example.com/feed/"),
    )
    assert with_password.status_code == 422

    missing = client.get("/sources/9999")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Source not found"


def test_html_source_cannot_keep_an_rss_feed(client):
    created = client.post("/sources", json=rss_payload(name="Switch Me"))
    source_id = created.json()["id"]
    switched = client.patch(f"/sources/{source_id}", json={"discovery_method": "html"})
    assert switched.status_code == 422
    assert client.get(f"/sources/{source_id}").json()["discovery_method"] == "rss"


def test_check_results_are_stored_and_cleared(client):
    created = client.post("/sources", json=rss_payload(name="Checked Publisher"))
    source_id = created.json()["id"]

    with Session(get_engine()) as session:
        record_source_check(session, source_id, success=False, error="x" * 800)

    failed = client.get(f"/sources/{source_id}").json()
    assert failed["last_checked_at"] is not None
    assert failed["last_success_at"] is None
    assert len(failed["last_error"]) == 500

    with Session(get_engine()) as session:
        record_source_check(session, source_id, success=True)

    recovered = client.get(f"/sources/{source_id}").json()
    assert recovered["last_success_at"] is not None
    assert recovered["last_error"] is None


def test_seed_is_idempotent(client):
    with Session(get_engine()) as session:
        first = seed_sources(session)
        second = seed_sources(session)

    catalog_names = {item.name for item in initial_sources()}
    listed = client.get("/sources").json()
    assert first == len(catalog_names)
    assert second == 0
    assert catalog_names <= {item["name"] for item in listed}
    assert client.get("/health").status_code == 200
