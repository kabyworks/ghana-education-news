"""Reader feed: ranked stories, category counts, and headline search."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.article import Article
from app.db.models.source import Source
from app.db.models.story import Story
from app.intelligence.feed.rank import rank_story
from app.services.story_service import StoryNotFoundError, get_story


@dataclass
class FeedStory:
    id: int
    title: str
    summary: str
    category: str
    published_at: datetime | None
    source_count: int
    sources: list[str]
    rank: float
    articles: list[tuple[Article, str]]


@dataclass(frozen=True)
class FeedCategory:
    name: str
    story_count: int


def list_feed(
    session: Session,
    *,
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
    now: datetime | None = None,
) -> list[FeedStory]:
    ranked = _ranked(session, category=category, now=_clock(now))
    return ranked[offset : offset + limit]


def search_feed(
    session: Session,
    *,
    query: str,
    category: str | None = None,
    limit: int = 20,
    now: datetime | None = None,
) -> list[FeedStory]:
    terms = search_terms(query)
    if not terms:
        return []
    ranked = _ranked(session, category=category, now=_clock(now))
    matched = [story for story in ranked if _matches(story, terms)]
    return matched[:limit]


def get_feed_story(session: Session, story_id: int, *, now: datetime | None = None) -> FeedStory:
    story, articles = get_story(session, story_id)
    if not story.reader_visible:
        raise StoryNotFoundError
    ranked = _rank_one(story, articles, now=_clock(now))
    ranked.articles = articles
    return ranked


def list_categories(session: Session) -> list[FeedCategory]:
    rows = session.execute(
        select(Story.category, func.count())
        .where(Story.reader_visible.is_(True))
        .group_by(Story.category)
        .order_by(func.count().desc(), Story.category.asc())
    ).all()
    return [FeedCategory(name=name, story_count=count) for name, count in rows]


def search_terms(query: str) -> list[str]:
    return [term for term in re.findall(r"[a-z0-9]+", query.casefold()) if len(term) >= 2]


def _ranked(session: Session, *, category: str | None, now: datetime) -> list[FeedStory]:
    statement = select(Story).where(Story.reader_visible.is_(True))
    if category is not None:
        statement = statement.where(Story.category == category)
    stories = list(session.scalars(statement))
    if not stories:
        return []
    articles_by_story = _articles_for([story.id for story in stories], session)
    ranked = [_rank_one(story, articles_by_story.get(story.id, []), now=now) for story in stories]
    ranked.sort(key=lambda item: (item.rank, item.source_count, _sort_time(item.published_at), item.id), reverse=True)
    return ranked


def _articles_for(story_ids: list[int], session: Session) -> dict[int, list[tuple[Article, str]]]:
    rows = session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .where(Article.story_id.in_(story_ids))
        .order_by(Article.published_at.asc().nulls_last(), Article.id.asc())
    ).all()
    grouped: dict[int, list[tuple[Article, str]]] = {}
    for article, source_name in rows:
        grouped.setdefault(article.story_id, []).append((article, source_name))
    return grouped


def _rank_one(story: Story, articles: list[tuple[Article, str]], *, now: datetime) -> FeedStory:
    sources = sorted({name for _article, name in articles})
    scores = [article.relevance_score for article, _name in articles if article.relevance_score is not None]
    relevance = sum(scores) / len(scores) if scores else 0.0
    published_at = _latest_published(articles) or story.first_published_at
    settings = get_settings()
    score = rank_story(
        published_at=published_at,
        source_count=len(sources),
        relevance=relevance,
        now=now,
        recency_weight=settings.feed_rank_recency_weight,
        coverage_weight=settings.feed_rank_coverage_weight,
        relevance_weight=settings.feed_rank_relevance_weight,
        half_life_hours=settings.feed_recency_half_life_hours,
    )
    return FeedStory(
        id=story.id,
        title=story.editor_title or story.title,
        summary=story.editor_summary or story.summary,
        category=story.category,
        published_at=published_at,
        source_count=len(sources),
        sources=sources,
        rank=score,
        articles=articles,
    )


def _matches(story: FeedStory, terms: list[str]) -> bool:
    haystack = " ".join([story.title, story.summary, *(article.title for article, _name in story.articles)]).casefold()
    return all(re.search(rf"\b{re.escape(term)}\b", haystack) is not None for term in terms)


def story_image(articles: list[tuple[Article, str]]) -> str | None:
    """One publisher picture for the card, preferring the newest illustrated article."""
    chosen: str | None = None
    chosen_at: datetime | None = None
    for article, _name in articles:
        url = (article.image_url or "").strip()
        if not url.startswith(("http://", "https://")) or len(url) > 1000:
            continue
        when = article.published_at
        if chosen is None or (when is not None and (chosen_at is None or when >= chosen_at)):
            chosen = url
            chosen_at = when
    return chosen


def _latest_published(articles: list[tuple[Article, str]]) -> datetime | None:
    times = [article.published_at for article, _name in articles if article.published_at is not None]
    if not times:
        return None
    latest = max(times)
    if latest.tzinfo is None:
        return latest.replace(tzinfo=timezone.utc)
    return latest


def _clock(now: datetime | None) -> datetime:
    """Rank against the current hour so the list and a story page agree."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.replace(minute=0, second=0, microsecond=0)


def _sort_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
