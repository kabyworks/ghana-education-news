"""Apply relevance results to stored articles."""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.article import (
    PROCESSING_PUBLISHED,
    PROCESSING_REJECTED,
    PROCESSING_REVIEW,
    Article,
)
from app.db.models.source import Source
from app.intelligence.relevance.scorer import RelevanceResult, score_text

logger = logging.getLogger(__name__)

_STATUS = {
    "publish": PROCESSING_PUBLISHED,
    "reject": PROCESSING_REJECTED,
    "review": PROCESSING_REVIEW,
}


@dataclass(frozen=True)
class RelevanceReport:
    considered: int
    publish: int
    reject: int
    review: int


def apply_relevance(article: Article, session: Session) -> RelevanceResult:
    source = session.get(Source, article.source_id)
    covers_ghana = True if source is None else bool(source.covers_ghana)
    result = score_text(article.title, article.excerpt, source_covers_ghana=covers_ghana)
    article.ghana_relevance = result.ghana_relevance
    article.education_relevance = result.education_relevance
    article.relevance_score = result.overall_relevance
    article.relevance_decision = result.decision
    article.relevance_reason = result.reason
    article.processing_status = _STATUS[result.decision]
    return result


def score_articles(session: Session, *, force: bool = False) -> RelevanceReport:
    statement = select(Article)
    if not force:
        statement = statement.where(Article.relevance_decision.is_(None))
    articles = list(session.scalars(statement))
    counts = {"publish": 0, "reject": 0, "review": 0}
    for article in articles:
        result = apply_relevance(article, session)
        counts[result.decision] += 1
    if articles:
        session.commit()
    logger.info(
        "Relevance scored %s articles publish=%s reject=%s review=%s",
        len(articles),
        counts["publish"],
        counts["reject"],
        counts["review"],
    )
    return RelevanceReport(considered=len(articles), **counts)
