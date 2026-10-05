"""Tests for the local review desk."""

from sqlalchemy.orm import Session

from app.db.database import get_engine
from app.ingestion.pipeline import run_ingestion
from tests.test_ingestion import MapFeedClient, feed_xml, rss_source


def test_review_desk_approves_rejects_edits_and_hides(client):
    rss_source(client, "Desk One", "https://one.example/feed/")
    feeds = {
        "https://one.example/feed/": feed_xml(
            {
                "title": "School team prepares for weekend fixture",
                "link": "https://one.example/fixture",
                "description": "The Accra side trains every evening.",
                "pub_date": "Mon, 05 Oct 2026 09:00:00 GMT",
            },
            {
                "title": "Keta MP commissions a kindergarten classroom",
                "link": "https://one.example/kindergarten",
                "description": "The new kindergarten replaces an unsafe structure.",
                "pub_date": "Mon, 05 Oct 2026 12:00:00 GMT",
            },
        )
    }
    with Session(get_engine()) as session:
        run_ingestion(session, MapFeedClient(feeds), force=True)

    page = client.get("/review")
    assert page.status_code == 200
    assert "Review desk" in page.text
    assert "text/html" in page.headers["content-type"]

    queue = client.get("/review/queue").json()
    assert [item["title"] for item in queue] == ["School team prepares for weekend fixture"]
    assert "content" not in queue[0]
    held_id = queue[0]["id"]

    feed = client.get("/feed").json()
    assert len(feed) == 1
    kindergarten = feed[0]
    assert kindergarten["category"] == "basic_schools"

    approved = client.post(f"/review/articles/{held_id}/approve")
    assert approved.status_code == 200
    assert len(client.get("/feed").json()) == 2
    assert client.get("/review/queue").json() == []

    hidden = client.post(f"/review/stories/{kindergarten['id']}/hide")
    assert hidden.status_code == 200
    assert hidden.json()["reader_visible"] is False
    assert all(item["id"] != kindergarten["id"] for item in client.get("/feed").json())
    assert client.get(f"/feed/{kindergarten['id']}").status_code == 404

    shown = client.post(f"/review/stories/{kindergarten['id']}/show")
    assert shown.json()["reader_visible"] is True
    assert any(item["id"] == kindergarten["id"] for item in client.get("/feed").json())

    edited = client.patch(
        f"/review/stories/{kindergarten['id']}",
        json={"title": "Keta kindergarten opens", "summary": "A local reviewer shortened this summary."},
    )
    assert edited.status_code == 200
    assert edited.json()["title_edited"] is True
    visible = client.get(f"/feed/{kindergarten['id']}").json()
    assert visible["title"] == "Keta kindergarten opens"
    assert visible["summary"] == "A local reviewer shortened this summary."
    assert "content" not in visible

    again = {
        "https://one.example/feed/": feed_xml(
            {
                "title": "School team prepares for weekend fixture",
                "link": "https://one.example/fixture",
                "description": "The Accra side trains every evening.",
                "pub_date": "Mon, 05 Oct 2026 09:00:00 GMT",
            },
            {
                "title": "Keta MP commissions a kindergarten classroom",
                "link": "https://one.example/kindergarten",
                "description": "The new kindergarten replaces an unsafe structure.",
                "pub_date": "Mon, 05 Oct 2026 12:00:00 GMT",
            },
            {
                "title": "Keta MP commissions the kindergarten classroom block",
                "link": "https://one.example/kindergarten-block",
                "description": "The classroom block is now open.",
                "pub_date": "Tue, 06 Oct 2026 12:00:00 GMT",
            },
        )
    }
    with Session(get_engine()) as session:
        run_ingestion(session, MapFeedClient(again), force=True)
    after_fetch = client.get(f"/feed/{kindergarten['id']}").json()
    assert after_fetch["title"] == "Keta kindergarten opens"
    assert len(after_fetch["articles"]) == 2

    cleared = client.patch(f"/review/stories/{kindergarten['id']}", json={"title": ""})
    assert cleared.json()["title_edited"] is False
    assert cleared.json()["title"] == kindergarten["title"]

    rejected = client.post(f"/review/articles/{held_id}/reject")
    assert rejected.status_code == 200
    titles = {item["title"] for item in client.get("/feed").json()}
    assert "School team prepares for weekend fixture" not in titles
    assert client.post("/review/articles/9999/approve").status_code == 404
    assert client.patch(f"/review/stories/{kindergarten['id']}", json={}).status_code == 422
    long_summary = "word " * 300
    assert client.patch(f"/review/stories/{kindergarten['id']}", json={"summary": long_summary}).status_code == 422
