"""Tests for story grouping, categories, and extractive summaries."""

from datetime import datetime, timedelta, timezone

from app.intelligence.stories.categories import categorize
from app.intelligence.stories.cluster import same_story
from app.intelligence.stories.summary import extractive_summary
from tests.test_ingestion import MapFeedClient, feed_xml, rss_source
from app.db.database import get_engine
from app.ingestion.pipeline import run_ingestion
from sqlalchemy.orm import Session


class _Item:
    def __init__(self, title: str, published_at: datetime) -> None:
        self.title = title
        self.published_at = published_at
        self.discovered_at = published_at


def test_categories_follow_the_strongest_topic():
    assert categorize("BECE results will be released on Friday") == "examinations"
    assert categorize("Teacher unions remain on strike over arrears") == "teachers"
    assert categorize("GTEC directs colleges to open admissions") == "higher_education"
    assert categorize("The MP commissioned a kindergarten classroom block") == "basic_schools"
    assert categorize("Desks are rotting in an abandoned E-Block senior high") == "basic_schools"
    assert categorize("A note about the weather") == "general"


def test_summary_is_taken_from_the_excerpt_only():
    excerpt = (
        "Union leaders say the strike continues until arrears are paid. "
        "Schools remain closed. "
        "A third sentence should stay out of a short summary."
    )
    summary = extractive_summary(excerpt, limit=120)
    assert summary == "Union leaders say the strike continues until arrears are paid. Schools remain closed."
    assert "<" not in summary
    long_sentence = "word " * 80
    clipped = extractive_summary(long_sentence, limit=40)
    assert clipped.endswith("...")
    assert len(clipped) <= 40
    assert clipped[:-3].strip() in " ".join(long_sentence.split())


def test_strike_headlines_match_and_separate_college_stories_do_not():
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    strike_a = _Item("Teacher unions declare a nationwide strike", now)
    strike_b = _Item("GES urges striking teachers to return to work", now + timedelta(days=2))
    old_strike = _Item("Teachers begin a nationwide strike", now - timedelta(days=30))
    principal = _Item("GTEC welcomes the new principal of St Francis College", now)
    admissions = _Item("GTEC directs colleges of education to begin admissions", now)
    assert same_story(strike_a, strike_b) is True
    assert same_story(strike_a, old_strike) is False
    assert same_story(principal, admissions) is False


def test_published_strike_articles_become_one_story_and_rejects_stay_out(client):
    desk = rss_source(client, "Desk One", "https://one.example/feed/")
    other = rss_source(client, "Desk Two", "https://two.example/feed/")
    assert client.patch(f"/sources/{desk['id']}", json={"trust_score": 0.9}).status_code == 200
    feeds = {
        "https://one.example/feed/": feed_xml(
            {
                "title": "Teacher unions declare a nationwide strike",
                "link": "https://one.example/strike",
                "description": (
                    "Union leaders say the strike continues until arrears are paid. "
                    "Schools in Accra remain closed."
                ),
                "pub_date": "Mon, 05 Oct 2026 10:00:00 GMT",
            },
            {
                "title": "Black Stars beat Nigeria in Kumasi",
                "link": "https://one.example/sports",
                "description": "The match ended two goals to one.",
                "pub_date": "Mon, 05 Oct 2026 11:00:00 GMT",
            },
        ),
        "https://two.example/feed/": feed_xml(
            {
                "title": "GES urges striking teachers to return to work",
                "link": "https://two.example/strike",
                "description": "The service warned that the academic calendar is at risk.",
                "pub_date": "Tue, 06 Oct 2026 10:00:00 GMT",
            },
            {
                "title": "GTEC welcomes the new principal of St Francis College",
                "link": "https://two.example/principal",
                "description": "The commission met the new principal in Accra on Monday.",
                "pub_date": "Tue, 06 Oct 2026 12:00:00 GMT",
            },
        ),
    }
    with Session(get_engine()) as session:
        run_ingestion(session, MapFeedClient(feeds), force=True)

    stories = client.get("/stories?limit=20").json()
    assert len(stories) == 2
    strike = next(item for item in stories if item["category"] == "teachers")
    college = next(item for item in stories if item["category"] == "higher_education")
    assert strike["article_count"] == 2
    assert college["article_count"] == 1
    assert strike["summary"] == (
        "Union leaders say the strike continues until arrears are paid. Schools in Accra remain closed."
    )
    assert "Black Stars" not in strike["title"]
    assert "Black Stars" not in college["title"]

    detail = client.get(f"/stories/{strike['id']}").json()
    assert {item["source_name"] for item in detail["articles"]} == {"Desk One", "Desk Two"}
    assert all(item["excerpt"] for item in detail["articles"])
    assert "content" not in detail

    articles = client.get("/articles?limit=20").json()
    sports = next(item for item in articles if item["title"] == "Black Stars beat Nigeria in Kumasi")
    assert sports["relevance_decision"] == "reject"
    assert sports["story_id"] is None

    again = client.post("/stories/build").json()
    assert again["considered"] == 0
    assert again["created"] == 0
    assert client.get("/stories?category=nope").status_code == 422
    assert client.get("/stories/9999").status_code == 404
    assert client.get("/stories?category=teachers").json()[0]["id"] == strike["id"]
    assert other["id"] != desk["id"]
