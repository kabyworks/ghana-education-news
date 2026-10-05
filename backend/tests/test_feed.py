"""Tests for the reader feed: rank, search, and a response without article bodies."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.database import get_engine
from app.ingestion.pipeline import run_ingestion
from app.intelligence.feed.rank import rank_story
from tests.test_ingestion import MapFeedClient, feed_xml, rss_source


def test_more_publishers_rank_above_a_single_source_when_equally_fresh():
    now = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    covered = rank_story(published_at=now, source_count=3, relevance=0.7, now=now)
    single = rank_story(published_at=now, source_count=1, relevance=0.7, now=now)
    assert covered > single


def test_a_fresh_story_outranks_old_coverage():
    now = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    fresh = rank_story(published_at=now, source_count=1, relevance=0.7, now=now)
    old = rank_story(published_at=now - timedelta(days=10), source_count=3, relevance=0.9, now=now)
    assert fresh > old


def test_feed_ranks_coverage_and_search_stays_on_headlines(client):
    first = rss_source(client, "Desk One", "https://one.example/feed/")
    second = rss_source(client, "Desk Two", "https://two.example/feed/")
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
    with Session(get_engine()) as session:
        run_ingestion(session, MapFeedClient(feeds), force=True)

    feed = client.get("/feed").json()
    assert [item["source_count"] for item in feed] == [2, 1]
    assert feed[0]["rank"] > feed[1]["rank"]
    assert feed[0]["category"] == "teachers"
    assert feed[0]["published_at"].startswith("2026-10-05")
    assert set(feed[0]["sources"]) == {"Desk One", "Desk Two"}
    assert "excerpt" not in feed[0]
    assert "content" not in feed[0]
    assert "relevance_reason" not in feed[0]

    teachers = client.get("/feed?category=teachers").json()
    assert len(teachers) == 1
    assert teachers[0]["id"] == feed[0]["id"]
    assert client.get("/feed?category=nope").status_code == 422
    assert client.get("/feed?offset=1").json()[0]["id"] == feed[1]["id"]

    categories = client.get("/feed/categories").json()
    counts = {item["name"]: item["story_count"] for item in categories}
    assert counts["teachers"] == 1
    assert counts["basic_schools"] == 1

    by_member_headline = client.get("/feed/search?q=abosamso").json()
    assert len(by_member_headline) == 1
    assert by_member_headline[0]["id"] == feed[0]["id"]
    assert "Abosamso" not in by_member_headline[0]["title"]

    kindergarten = client.get("/feed/search?q=kindergarten").json()
    assert len(kindergarten) == 1
    assert kindergarten[0]["category"] == "basic_schools"
    assert client.get("/feed/search?q=a").status_code == 422

    detail = client.get(f"/feed/{feed[0]['id']}").json()
    assert detail["rank"] == feed[0]["rank"]
    assert len(detail["articles"]) == 2
    assert {item["source_name"] for item in detail["articles"]} == {"Desk One", "Desk Two"}
    for article in detail["articles"]:
        assert set(article) == {"source_name", "title", "url", "published_at", "excerpt"}
        assert article["excerpt"]
        assert "<" not in article["excerpt"]
    assert "content" not in detail
    assert "relevance_reason" not in detail
    assert client.get("/feed/9999").status_code == 404
    assert first["id"] != second["id"]
