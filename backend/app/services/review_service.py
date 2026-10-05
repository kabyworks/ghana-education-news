"""Local review actions. These do not fetch article pages."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.article import (
    PROCESSING_PUBLISHED,
    PROCESSING_REJECTED,
    Article,
)
from app.db.models.source import Source
from app.db.models.story import Story
from app.intelligence.stories.service import build_stories, resync_story
from app.services.article_service import ArticleNotFoundError
from app.services.story_service import StoryNotFoundError

logger = logging.getLogger(__name__)

TITLE_LIMIT = 500
SUMMARY_LIMIT = 1000


class InvalidReviewError(Exception):
    """The review change cannot be stored."""

    def __init__(self, detail: str) -> None:
        self.detail = detail


def list_queue(session: Session) -> list[tuple[Article, str]]:
    rows = session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .where(Article.relevance_decision == "review")
        .order_by(Article.published_at.desc().nulls_last(), Article.id.desc())
    ).all()
    return [(article, name) for article, name in rows]


def list_review_stories(session: Session) -> list[Story]:
    return list(session.scalars(select(Story).order_by(Story.reader_visible.desc(), Story.updated_at.desc(), Story.id.desc())))


def approve_article(session: Session, article_id: int) -> Article:
    article = _article(session, article_id)
    now = datetime.now(timezone.utc)
    article.relevance_decision = "publish"
    article.processing_status = PROCESSING_PUBLISHED
    article.relevance_reason = _note(article.relevance_reason, "approved")
    article.updated_at = now
    session.commit()
    build_stories(session)
    session.refresh(article)
    logger.info("Review desk approved article %s", article_id)
    return article


def reject_article(session: Session, article_id: int) -> Article:
    article = _article(session, article_id)
    story_id = article.story_id
    now = datetime.now(timezone.utc)
    article.relevance_decision = "reject"
    article.processing_status = PROCESSING_REJECTED
    article.story_id = None
    article.relevance_reason = _note(article.relevance_reason, "rejected")
    article.updated_at = now
    session.flush()
    if story_id is not None:
        resync_story(session, story_id)
    session.commit()
    logger.info("Review desk rejected article %s", article_id)
    return article


def set_story_visible(session: Session, story_id: int, *, visible: bool) -> Story:
    story = _story(session, story_id)
    story.reader_visible = visible
    story.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(story)
    logger.info("Review desk set story %s reader_visible=%s", story_id, visible)
    return story


def edit_story(session: Session, story_id: int, *, title: str | None, summary: str | None) -> Story:
    if title is None and summary is None:
        raise InvalidReviewError("Provide a title or a summary")
    story = _story(session, story_id)
    if title is not None:
        story.editor_title = _edited_text(title, TITLE_LIMIT, "Title")
    if summary is not None:
        story.editor_summary = _edited_text(summary, SUMMARY_LIMIT, "Summary")
    story.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(story)
    logger.info("Review desk edited story %s", story_id)
    return story


def _article(session: Session, article_id: int) -> Article:
    article = session.get(Article, article_id)
    if article is None:
        raise ArticleNotFoundError
    return article


def _story(session: Session, story_id: int) -> Story:
    story = session.get(Story, story_id)
    if story is None:
        raise StoryNotFoundError
    return story


def _edited_text(value: str, limit: int, label: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > limit:
        raise InvalidReviewError(f"{label} must be {limit} characters or fewer")
    return cleaned


def _note(reason: str | None, action: str) -> str:
    text = f"{reason or ''} Review desk: {action}.".strip()
    return text[:500]
