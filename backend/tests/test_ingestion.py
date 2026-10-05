"""Tests for RSS ingestion."""

from sqlalchemy.orm import Session

import httpx2

from app.api.routes.ingestion import get_feed_client
from app.db.database import get_engine
from app.ingestion.client import USER_AGENT, FeedNotAllowedError, HttpxFeedClient
from app.ingestion.pipeline import IngestionBusyError, _run_lock, run_ingestion
from app.ingestion.robots import crawl_delay_seconds, feed_is_allowed
from app.ingestion.text import excerpt_from_html
from app.ingestion.urls import normalize_url


class MapFeedClient:
    def __init__(self, feeds: dict[str, bytes | Exception]) -> None:
        self.feeds = feeds

    def get_feed(self, url: str) -> bytes:
        value = self.feeds[url]
        if isinstance(value, Exception):
            raise value
        return value


def rss_source(client, name: str, feed_url: str):
    response = client.post(
        "/sources",
        json={
            "name": name,
            "base_url": "https://example.com/",
            "feed_url": feed_url,
            "source_type": "news",
            "trust_score": 0.5,
            "crawl_frequency_minutes": 180,
            "discovery_method": "rss",
        },
    )
    assert response.status_code == 201
    return response.json()


def feed_xml(*items: dict[str, str]) -> bytes:
    body = ["<?xml version='1.0' encoding='UTF-8'?>", "<rss version='2.0'><channel><language>en</language>"]
    for item in items:
        body.append("<item>")
        body.append(f"<title>{item['title']}</title>")
        if item.get("link"):
            body.append(f"<link>{item['link']}</link>")
        if item.get("description"):
            body.append(f"<description><![CDATA[{item['description']}]]></description>")
        if item.get("pub_date"):
            body.append(f"<pubDate>{item['pub_date']}</pubDate>")
        if item.get("author"):
            body.append(f"<author>{item['author']}</author>")
        body.append("</item>")
    body.append("</channel></rss>")
    return "".join(body).encode()


def test_normalize_url_drops_tracking_and_fragments():
    normalized = normalize_url("HTTPS://Example.com/stories/ges/?utm_source=rss&id=4#top")
    assert normalized == "https://example.com/stories/ges?id=4"


def test_excerpt_is_plain_text_and_capped():
    excerpt = excerpt_from_html("<p>Hello <b>Ghana</b></p>" + (" word" * 400))
    assert excerpt is not None
    assert "<" not in excerpt
    assert excerpt.startswith("Hello Ghana")
    assert len(excerpt) == 1000


def test_robots_rules():
    allowed = "User-agent: *\nDisallow: /private\nCrawl-delay: 90\n"
    blocked = "User-agent: *\nDisallow: /\n"
    assert feed_is_allowed(None, "https://example.com/feed/", USER_AGENT) is True
    assert feed_is_allowed(allowed, "https://example.com/feed/", USER_AGENT) is True
    assert feed_is_allowed(blocked, "https://example.com/feed/", USER_AGENT) is False
    assert crawl_delay_seconds(allowed, USER_AGENT) == 30
    assert crawl_delay_seconds(None, USER_AGENT) == 0


def test_feed_client_respects_robots_and_reads_a_feed():
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/robots.txt":
            return httpx2.Response(200, text="User-agent: *\nDisallow: /secret\n")
        return httpx2.Response(200, content=b"<rss><channel></channel></rss>")

    client = HttpxFeedClient(transport=httpx2.MockTransport(handler))
    assert client.get_feed("https://example.com/feed/") == b"<rss><channel></channel></rss>"

    def blocked(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/robots.txt":
            return httpx2.Response(200, text="User-agent: *\nDisallow: /\n")
        return httpx2.Response(200, content=b"unused")

    blocked_client = HttpxFeedClient(transport=httpx2.MockTransport(blocked))
    try:
        blocked_client.get_feed("https://example.com/feed/")
    except FeedNotAllowedError:
        return
    raise AssertionError("disallowed feed was fetched")


def test_feed_client_asks_for_uncompressed_bytes():
    seen: dict[str, str] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["encoding"] = request.headers.get("accept-encoding", "")
        if request.url.path == "/robots.txt":
            return httpx2.Response(404)
        return httpx2.Response(200, content=b"<rss></rss>")

    HttpxFeedClient(transport=httpx2.MockTransport(handler)).get_feed("https://example.com/feed/")
    assert seen["encoding"] == "identity"


def test_ingestion_stores_articles_from_multiple_sources_and_skips_duplicates(client):
    first = rss_source(client, "Desk One", "https://one.example/feed/")
    second = rss_source(client, "Desk Two", "https://two.example/feed/")
    assert client.patch(f"/sources/{second['id']}", json={"covers_ghana": False}).status_code == 200
    feeds = {
        "https://one.example/feed/": feed_xml(
            {
                "title": "GES opens placement",
                "link": "https://one.example/stories/placement?utm_source=rss",
                "description": "<p>Placement starts <b>Monday</b>.</p>",
                "pub_date": "Mon, 05 Oct 2026 10:00:00 GMT",
                "author": "News Desk",
            },
            {"title": "No link here", "description": "Ignored"},
        ),
        "https://two.example/feed/": feed_xml(
            {
                "title": "University admissions update",
                "link": "https://two.example/admissions",
                "description": "Applications are open.",
            },
            {
                "title": "Same placement link",
                "link": "https://one.example/stories/placement/",
                "description": "Repeated address.",
            },
        ),
    }
    with Session(get_engine()) as session:
        report = run_ingestion(session, MapFeedClient(feeds), force=True)

    assert report.sources_succeeded == 2
    assert report.articles_stored == 2
    assert report.duplicates_skipped == 1
    articles = client.get("/articles").json()
    assert len(articles) == 2
    titles = {item["title"] for item in articles}
    assert titles == {"GES opens placement", "University admissions update"}
    placement = next(item for item in articles if item["title"] == "GES opens placement")
    assert placement["canonical_url"] == "https://one.example/stories/placement"
    assert placement["excerpt"] == "Placement starts Monday."
    assert placement["author"] == "News Desk"
    assert placement["processing_status"] == "published"
    assert placement["relevance_decision"] == "publish"
    assert placement["relevance_score"] is not None
    assert placement["relevance_score"] >= 0.6
    admissions = next(item for item in articles if item["title"] == "University admissions update")
    assert admissions["relevance_decision"] == "reject"
    assert "<" not in (placement["excerpt"] or "")
    assert client.get(f"/sources/{first['id']}").json()["last_error"] is None
    assert client.get(f"/sources/{second['id']}").json()["last_success_at"] is not None

    with Session(get_engine()) as session:
        again = run_ingestion(session, MapFeedClient(feeds), force=False)
    assert again.articles_stored == 0
    assert all(item.status == "skipped" and item.error == "not due" for item in again.results if item.source_id in {first["id"], second["id"]})

    with Session(get_engine()) as session:
        forced = run_ingestion(session, MapFeedClient(feeds), force=True)
    assert forced.articles_stored == 0
    assert forced.duplicates_skipped == 3


def test_one_broken_source_does_not_stop_the_other(client):
    broken = rss_source(client, "Broken Desk", "https://broken.example/feed/")
    healthy = rss_source(client, "Healthy Desk", "https://healthy.example/feed/")
    feeds = {
        "https://broken.example/feed/": TimeoutError("timed out"),
        "https://healthy.example/feed/": feed_xml(
            {"title": "Scholarship list", "link": "https://healthy.example/scholarships", "description": "Ten awards."}
        ),
    }
    with Session(get_engine()) as session:
        report = run_ingestion(session, MapFeedClient(feeds), force=True)

    by_id = {item.source_id: item for item in report.results}
    assert by_id[broken["id"]].status == "failed"
    assert "timed out" in (by_id[broken["id"]].error or "")
    assert by_id[healthy["id"]].status == "succeeded"
    assert by_id[healthy["id"]].articles_stored == 1
    assert client.get(f"/sources/{broken['id']}").json()["last_error"]
    titles = [item["title"] for item in client.get("/articles").json()]
    assert titles == ["Scholarship list"]


def test_inactive_and_feedless_sources_are_skipped(client):
    paused = rss_source(client, "Paused Desk", "https://paused.example/feed/")
    client.patch(f"/sources/{paused['id']}", json={"active": False})
    html_source = client.post(
        "/sources",
        json={
            "name": "Page Only",
            "base_url": "https://pages.example/",
            "source_type": "government",
            "trust_score": 0.9,
            "crawl_frequency_minutes": 1440,
            "discovery_method": "html",
            "parser_key": "none",
        },
    )
    assert html_source.status_code == 201
    with Session(get_engine()) as session:
        report = run_ingestion(session, MapFeedClient({}), force=True)
    reasons = {item.source_name: item.error for item in report.results}
    assert reasons["Paused Desk"] == "inactive"
    assert reasons["Page Only"] == "no rss feed"
    assert client.get("/articles").json() == []


def test_source_with_articles_cannot_be_deleted(client):
    source = rss_source(client, "Kept Desk", "https://kept.example/feed/")
    feeds = {
        "https://kept.example/feed/": feed_xml(
            {"title": "Teacher update", "link": "https://kept.example/teachers", "description": "A meeting."}
        )
    }
    with Session(get_engine()) as session:
        run_ingestion(session, MapFeedClient(feeds), force=True)
    deleted = client.delete(f"/sources/{source['id']}")
    assert deleted.status_code == 409
    assert deleted.json()["detail"] == "This source still has articles"
    assert client.get(f"/sources/{source['id']}").status_code == 200


def test_run_endpoint_uses_the_injected_client(client):
    rss_source(client, "Endpoint Desk", "https://endpoint.example/feed/")
    fake = MapFeedClient(
        {
            "https://endpoint.example/feed/": feed_xml(
                {"title": "From the endpoint", "link": "https://endpoint.example/story", "description": "Ready."}
            )
        }
    )
    client.app.dependency_overrides[get_feed_client] = lambda: fake
    response = client.post("/ingestion/run")
    assert response.status_code == 200
    body = response.json()
    assert body["articles_stored"] == 1
    assert client.get("/articles").json()[0]["title"] == "From the endpoint"


def test_ingestion_rejects_a_second_overlapping_run(client):
    _run_lock.acquire()
    try:
        with Session(get_engine()) as session:
            try:
                run_ingestion(session, MapFeedClient({}), force=True)
            except IngestionBusyError:
                return
    finally:
        _run_lock.release()
    raise AssertionError("overlapping run was accepted")
