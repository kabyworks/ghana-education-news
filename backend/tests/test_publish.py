"""The phone snapshot is a summary plus publisher links, and an empty export cannot erase it."""

import json

import pytest
from sqlalchemy.orm import Session

from app.db.database import get_engine
from app.ingestion.pipeline import run_ingestion
from app.publish.snapshot import SnapshotRefused, publish_snapshot
from tests.test_ingestion import MapFeedClient, feed_xml, rss_source


def test_publish_writes_the_phone_site_and_keeps_the_last_good_copy(client, tmp_path):
    rss_source(client, "Desk One", "https://one.example/feed/")
    rss_source(client, "Desk Two", "https://two.example/feed/")
    feeds = {
        "https://one.example/feed/": feed_xml(
            {
                "title": "Teacher unions declare a nationwide strike",
                "link": "https://one.example/strike",
                "description": "Union leaders say the strike continues until arrears are paid.",
                "pub_date": "Thu, 25 Sep 2026 10:00:00 GMT",
            }
        ),
        "https://two.example/feed/": feed_xml(
            {
                "title": "Abosamso assemblyman takes over a classroom during the teacher strike",
                "link": "https://two.example/abosamso",
                "description": "Parents said the classroom was opened for the children.",
                "pub_date": "Mon, 05 Oct 2026 11:00:00 GMT",
            },
            {
                "title": "Keta MP commissions a kindergarten classroom",
                "link": "https://two.example/kindergarten",
                "description": "The new kindergarten replaces an unsafe structure in the community.",
                "pub_date": "Mon, 05 Oct 2026 12:00:00 GMT",
            },
        ),
    }
    destination = tmp_path / "site"
    with Session(get_engine()) as session:
        run_ingestion(session, MapFeedClient(feeds), force=True)
        publish_snapshot(session, destination)

    page = (destination / "index.html").read_text(encoding="utf-8")
    assert 'data-feed="static"' in page
    assert 'href="manifest.webmanifest"' in page
    assert "/app/" not in page
    assert not (destination / "desk.html").exists()
    assert (destination / ".nojekyll").is_file()
    assert "data/feed.json" in (destination / "app.js").read_text(encoding="utf-8")

    worker = (destination / "sw.js").read_text(encoding="utf-8")
    assert "ghanaed-phone-2" in worker
    assert "./data/feed.json" in worker

    manifest = json.loads((destination / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "./"
    assert manifest["scope"] == "./"
    assert manifest["icons"][0]["src"] == "icon-192.png"

    feed = json.loads((destination / "data" / "feed.json").read_text(encoding="utf-8"))
    assert feed["generated_at"]
    assert {item["name"] for item in feed["categories"]} == {"teachers", "basic_schools"}
    assert [story["category"] for story in feed["stories"]] == ["teachers", "basic_schools"]
    strike = feed["stories"][0]
    assert {article["title"] for article in strike["articles"]} >= {
        "Teacher unions declare a nationwide strike",
        "Abosamso assemblyman takes over a classroom during the teacher strike",
    }
    for story in feed["stories"]:
        assert "content" not in story
        assert "relevance_reason" not in story
        for article in story["articles"]:
            assert set(article) == {"source_name", "title", "url", "published_at", "excerpt"}
            assert article["excerpt"]
            assert len(article["excerpt"]) <= 1000
            assert "<" not in article["excerpt"]

    story_id = strike["id"]
    edited = client.patch(f"/review/stories/{story_id}", json={"title": "Edited for the phone"})
    assert edited.status_code == 200
    with Session(get_engine()) as session:
        publish_snapshot(session, destination)
    updated = json.loads((destination / "data" / "feed.json").read_text(encoding="utf-8"))
    assert updated["stories"][0]["title"] == "Edited for the phone"

    for story in updated["stories"]:
        assert client.post(f"/review/stories/{story['id']}/hide").status_code == 200
    with Session(get_engine()) as session:
        with pytest.raises(SnapshotRefused):
            publish_snapshot(session, destination)
    kept = json.loads((destination / "data" / "feed.json").read_text(encoding="utf-8"))
    assert kept["stories"][0]["title"] == "Edited for the phone"
    assert len(kept["stories"]) == 2
