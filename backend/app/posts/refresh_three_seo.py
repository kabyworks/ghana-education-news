"""Refresh today's three tip posts with big-text images and stronger SEO copy."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_engine
from app.db.models.article import Article
from app.db.models.story import Story
from app.publish.snapshot import publish_snapshot

UPDATES = [
    {
        "id": 790,
        "image": "https://edulens360.com/images/tips/wassce-essay-v2.png",
        "summary": (
            "Learn how to answer WASSCE essay questions in Ghana: command words, "
            "quick planning, paragraph structure, examples, and timing tips to score more marks."
        ),
        "related": (
            "\n\n### Related Edulens360 tips\n"
            "GES promotion interview questions teachers should prepare for: "
            "https://edulens360.com/story/791/ges-promotion-interview-questions-teachers-should-prepare-for/\n"
            "CSSPS school placement: what to do if you are not satisfied: "
            "https://edulens360.com/story/792/cssps-school-placement-what-to-do-if-you-are-not-satisfied/"
        ),
    },
    {
        "id": 791,
        "image": "https://edulens360.com/images/tips/ges-promotion-v2.png",
        "summary": (
            "Prepare for GES promotion interviews in Ghana with common questions on teaching practice, "
            "professionalism, education issues, judgment, and how to answer with classroom examples."
        ),
        "related": (
            "\n\n### Related Edulens360 tips\n"
            "How to answer WASSCE essay questions to score more marks: "
            "https://edulens360.com/story/790/how-to-answer-wassce-essay-questions-to-score-more-marks/\n"
            "CSSPS school placement: what to do if you are not satisfied: "
            "https://edulens360.com/story/792/cssps-school-placement-what-to-do-if-you-are-not-satisfied/"
        ),
    },
    {
        "id": 792,
        "image": "https://edulens360.com/images/tips/cssps-placement-v2.png",
        "summary": (
            "CSSPS school placement help for students and parents in Ghana: confirm your placement, "
            "use official self-placement options, contact the right office, and avoid costly mistakes."
        ),
        "related": (
            "\n\n### Related Edulens360 tips\n"
            "How to answer WASSCE essay questions to score more marks: "
            "https://edulens360.com/story/790/how-to-answer-wassce-essay-questions-to-score-more-marks/\n"
            "GES promotion interview questions teachers should prepare for: "
            "https://edulens360.com/story/791/ges-promotion-interview-questions-teachers-should-prepare-for/"
        ),
    },
]


def main() -> None:
    now = datetime.now(timezone.utc)
    with Session(get_engine()) as session:
        for index, item in enumerate(UPDATES):
            story = session.get(Story, item["id"])
            if story is None:
                raise SystemExit(f"missing story {item['id']}")
            article = session.scalar(select(Article).where(Article.story_id == item["id"]))
            if article is None:
                raise SystemExit(f"missing article for story {item['id']}")
            when = now - timedelta(seconds=index * 40)
            story.editor_summary = item["summary"]
            story.summary = item["summary"]
            story.first_published_at = when
            story.updated_at = when
            excerpt = article.excerpt or ""
            if "### Related Edulens360 tips" not in excerpt:
                article.excerpt = excerpt.rstrip() + item["related"]
            article.image_url = item["image"]
            article.published_at = when
            article.updated_at = when
            session.commit()
            print(f"updated {item['id']} -> {item['image']}")
        catalog = publish_snapshot(session, Path(__file__).resolve().parents[3] / "docs")
    print("published", len(catalog["stories"]))
    print("top", [(s["id"], s["title"][:42], s.get("image_url")) for s in catalog["stories"][:3]])


if __name__ == "__main__":
    main()
