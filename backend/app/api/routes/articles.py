"""Stored articles discovered from source feeds."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.intelligence.relevance.scorer import DECISIONS
from app.schemas.ingestion import ArticleRead
from app.services.article_service import ArticleNotFoundError, get_article, list_articles

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=list[ArticleRead])
def read_articles(
    source_id: int | None = None,
    decision: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
) -> list[ArticleRead]:
    if decision is not None and decision not in DECISIONS:
        allowed = ", ".join(sorted(DECISIONS))
        raise HTTPException(status_code=422, detail=f"decision must be one of: {allowed}")
    return [
        _article_read(article, source_name)
        for article, source_name in list_articles(session, source_id=source_id, decision=decision, limit=limit)
    ]


@router.get("/{article_id}", response_model=ArticleRead)
def read_article(article_id: int, session: Session = Depends(get_db)) -> ArticleRead:
    try:
        article, source_name = get_article(session, article_id)
    except ArticleNotFoundError:
        raise HTTPException(status_code=404, detail="Article not found") from None
    return _article_read(article, source_name)


def _article_read(article, source_name: str) -> ArticleRead:
    return ArticleRead(
        id=article.id,
        source_id=article.source_id,
        source_name=source_name,
        title=article.title,
        url=article.url,
        canonical_url=article.canonical_url,
        author=article.author,
        published_at=article.published_at,
        discovered_at=article.discovered_at,
        excerpt=article.excerpt,
        image_url=article.image_url,
        processing_status=article.processing_status,
        ghana_relevance=article.ghana_relevance,
        education_relevance=article.education_relevance,
        relevance_score=article.relevance_score,
        relevance_decision=article.relevance_decision,
        relevance_reason=article.relevance_reason,
        story_id=article.story_id,
        content_hash=article.content_hash,
    )
