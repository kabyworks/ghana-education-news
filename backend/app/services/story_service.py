"""Read grouped stories."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.article import Article
from app.db.models.source import Source
from app.db.models.story import Story


class StoryNotFoundError(Exception):
    """The requested story id is not stored."""


def list_stories(session: Session, *, category: str | None = None, limit: int = 20) -> list[Story]:
    statement = select(Story).order_by(Story.first_published_at.desc().nulls_last(), Story.id.desc()).limit(limit)
    if category is not None:
        statement = statement.where(Story.category == category)
    return list(session.scalars(statement))


def get_story(session: Session, story_id: int) -> tuple[Story, list[tuple[Article, str]]]:
    story = session.get(Story, story_id)
    if story is None:
        raise StoryNotFoundError
    rows = session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .where(Article.story_id == story_id)
        .order_by(Article.published_at.asc().nulls_last(), Article.id.asc())
    ).all()
    return story, [(article, name) for article, name in rows]
