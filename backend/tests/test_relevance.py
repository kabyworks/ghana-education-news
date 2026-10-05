"""Tests for Ghana and education relevance rules."""

from app.intelligence.relevance.scorer import score_text


def test_clearly_relevant_article_is_published():
    result = score_text(
        "Government to recruit 16,000 teachers",
        "The Ghana Education Service says recruitment starts in Accra.",
    )
    assert result.decision == "publish"
    assert result.ghana_relevance >= 0.6
    assert result.education_relevance >= 0.6
    assert result.overall_relevance == min(result.ghana_relevance, result.education_relevance)
    assert "Decision: publish." in result.reason


def test_ghana_news_unrelated_to_education_is_rejected():
    result = score_text("Black Stars beat Nigeria in Kumasi", "The match ended two goals to one.")
    assert result.decision == "reject"
    assert result.ghana_relevance >= 0.6
    assert result.education_relevance < 0.35


def test_education_news_unrelated_to_ghana_is_rejected():
    result = score_text(
        "Harvard changes undergraduate admissions policy",
        "The university said the new rules start next year.",
    )
    assert result.decision == "reject"
    assert result.education_relevance >= 0.6
    assert result.ghana_relevance < 0.35


def test_international_education_news_is_rejected():
    result = score_text(
        "UK A-level students await results",
        "Schools in England will release grades on Thursday.",
    )
    assert result.decision == "reject"
    assert result.ghana_relevance < 0.35


def test_ambiguous_article_is_held_for_review():
    result = score_text(
        "School team prepares for weekend fixture",
        "The Accra side trains every evening.",
    )
    assert result.decision == "review"
    assert 0.35 <= result.ghana_relevance < 0.6
    assert 0.35 <= result.education_relevance < 0.6


def test_weak_school_mention_does_not_publish():
    result = score_text(
        "Old school music night draws crowds",
        "The Accra concert starts at 8.",
    )
    assert result.decision != "publish"


def test_ghana_source_keeps_teacher_news_and_still_rejects_sports():
    teachers = score_text(
        "Teachers declare a nationwide strike",
        "Union leaders say arrears have not been paid.",
        source_covers_ghana=True,
    )
    sports = score_text(
        "Black Stars beat Nigeria in Kumasi",
        "The match ended two goals to one.",
        source_covers_ghana=True,
    )
    assert teachers.decision == "publish"
    assert "Ghana source" in teachers.reason
    assert sports.decision == "reject"


def test_school_infrastructure_from_a_ghana_source_publishes():
    result = score_text(
        "MP commissions a kindergarten to replace an unsafe structure",
        "The new classrooms serve the community school.",
        source_covers_ghana=True,
    )
    assert result.decision == "publish"
    assert result.education_relevance >= 0.6


def test_one_incidental_education_word_stays_in_review():
    result = score_text(
        "Domestic tourism and its impact on the local economy",
        "The feature mentions education only in passing.",
        source_covers_ghana=True,
    )
    assert result.decision == "review"
    assert result.education_relevance < 0.6


def test_thresholds_can_be_changed_without_editing_terms():
    title = "School team prepares for weekend fixture"
    excerpt = "The Accra side trains every evening."
    held = score_text(title, excerpt, publish_threshold=0.6, reject_threshold=0.35)
    published = score_text(title, excerpt, publish_threshold=0.4, reject_threshold=0.2)
    assert held.decision == "review"
    assert published.decision == "publish"


def test_articles_can_be_filtered_by_decision(client):
    from tests.test_ingestion import feed_xml, rss_source

    rss_source(client, "Relevance Desk", "https://relevance.example/feed/")
    from sqlalchemy.orm import Session

    from app.db.database import get_engine
    from app.ingestion.pipeline import run_ingestion
    from tests.test_ingestion import MapFeedClient

    feeds = {
        "https://relevance.example/feed/": feed_xml(
            {
                "title": "GES to recruit teachers",
                "link": "https://relevance.example/teachers",
                "description": "Recruitment opens in Accra.",
            },
            {
                "title": "Black Stars win in Kumasi",
                "link": "https://relevance.example/match",
                "description": "The final was decided late.",
            },
        )
    }
    with Session(get_engine()) as session:
        run_ingestion(session, MapFeedClient(feeds), force=True)

    published = client.get("/articles", params={"decision": "publish"}).json()
    rejected = client.get("/articles", params={"decision": "reject"}).json()
    assert any(item["title"] == "GES to recruit teachers" for item in published)
    assert any(item["title"] == "Black Stars win in Kumasi" for item in rejected)
    assert client.get("/articles", params={"decision": "maybe"}).status_code == 422
