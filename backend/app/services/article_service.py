"""Read stored articles."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.article import Article
from app.db.models.source import Source


class ArticleNotFoundError(Exception):
    """The requested article id is not stored."""


def list_articles(
    session: Session,
    *,
    source_id: int | None = None,
    decision: str | None = None,
    limit: int = 20,
) -> list[tuple[Article, str]]:
    statement = (
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .order_by(Article.published_at.desc().nulls_last(), Article.id.desc())
        .limit(limit)
    )
    if source_id is not None:
        statement = statement.where(Article.source_id == source_id)
    if decision is not None:
        statement = statement.where(Article.relevance_decision == decision)
    return [(article, name) for article, name in session.execute(statement)]


def get_article(session: Session, article_id: int) -> tuple[Article, str]:
    row = session.execute(
        select(Article, Source.name).join(Source, Article.source_id == Source.id).where(Article.id == article_id)
    ).one_or_none()
    if row is None:
        raise ArticleNotFoundError
    article, name = row
    return article, name
