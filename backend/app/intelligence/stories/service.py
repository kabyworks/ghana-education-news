"""Build and refresh stories from articles marked publish."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db.models.article import Article
from app.db.models.source import Source
from app.db.models.story import Story
from app.intelligence.stories.categories import categorize
from app.intelligence.stories.cluster import representative_title, same_story
from app.intelligence.stories.summary import extractive_summary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoryReport:
    considered: int
    created: int
    attached: int
    stories: int


@dataclass
class _Group:
    story: Story
    members: list[tuple[Article, Source]] = field(default_factory=list)


def build_stories(session: Session, *, force: bool = False) -> StoryReport:
    if force:
        session.execute(update(Article).values(story_id=None))
        session.execute(delete(Story))
        session.flush()

    pending = _publish_rows(session, unassigned_only=True)
    groups = _existing_groups(session)
    created = 0
    attached = 0
    now = datetime.now(timezone.utc)
    for article, source in pending:
        match = next((group for group in groups if any(same_story(article, member) for member, _src in group.members)), None)
        if match is None:
            story = Story(
                title=article.title[:500],
                summary=article.title[:500],
                category="general",
                article_count=1,
                created_at=now,
                updated_at=now,
            )
            session.add(story)
            session.flush()
            article.story_id = story.id
            match = _Group(story=story, members=[(article, source)])
            groups.append(match)
            created += 1
        else:
            article.story_id = match.story.id
            match.members.append((article, source))
            attached += 1
        _refresh(match, now=now)
    if force or pending:
        session.commit()
    total = _count_stories(session)
    logger.info(
        "Stories considered=%s created=%s attached=%s total=%s",
        len(pending),
        created,
        attached,
        total,
    )
    return StoryReport(considered=len(pending), created=created, attached=attached, stories=total)


def _publish_rows(session: Session, *, unassigned_only: bool) -> list[tuple[Article, Source]]:
    statement = (
        select(Article, Source)
        .join(Source, Article.source_id == Source.id)
        .where(Article.relevance_decision == "publish")
        .order_by(Article.published_at.asc().nulls_last(), Article.id.asc())
    )
    if unassigned_only:
        statement = statement.where(Article.story_id.is_(None))
    return list(session.execute(statement))


def _existing_groups(session: Session) -> list[_Group]:
    rows = session.execute(
        select(Article, Source)
        .join(Source, Article.source_id == Source.id)
        .where(Article.story_id.is_not(None))
        .order_by(Article.published_at.asc().nulls_last(), Article.id.asc())
    ).all()
    stories = {story.id: story for story in session.scalars(select(Story))}
    grouped: dict[int, _Group] = {}
    for article, source in rows:
        story = stories.get(article.story_id)
        if story is None:
            continue
        group = grouped.get(story.id)
        if group is None:
            group = _Group(story=story)
            grouped[story.id] = group
        group.members.append((article, source))
    groups = list(grouped.values())
    groups.sort(key=lambda group: (_sort_time(group.story.first_published_at), group.story.id))
    return groups


def _refresh(group: _Group, *, now: datetime) -> None:
    members = group.members
    text = " ".join(f"{article.title} {article.excerpt or ''}" for article, _source in members)
    source_excerpt = _summary_source(members)
    summary = extractive_summary(source_excerpt[0].excerpt or "") if source_excerpt else ""
    if not summary:
        summary = members[0][0].title
    published = [_when_or_none(article) for article, _source in members]
    published = [value for value in published if value is not None]
    story = group.story
    story.title = representative_title([(article.title, source.trust_score) for article, source in members])[:500]
    story.summary = summary
    story.category = categorize(text)
    story.article_count = len(members)
    story.first_published_at = min(published) if published else None
    story.updated_at = now


def _summary_source(members: list[tuple[Article, Source]]) -> list[Article]:
    ranked = sorted(
        (article for article, source in members if article.excerpt),
        key=lambda article: (_trust(members, article), len(article.excerpt or "")),
        reverse=True,
    )
    return ranked


def _trust(members: list[tuple[Article, Source]], article: Article) -> float:
    for member, source in members:
        if member.id == article.id:
            return source.trust_score
    return 0.0


def _when_or_none(article: Article) -> datetime | None:
    value = article.published_at
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _sort_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.max.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _count_stories(session: Session) -> int:
    return len(session.scalars(select(Story.id)).all())


def resync_story(session: Session, story_id: int) -> None:
    """Refresh one story after a reviewer removes an article, or delete it when it is empty."""
    story = session.get(Story, story_id)
    if story is None:
        return
    rows = list(
        session.execute(
            select(Article, Source)
            .join(Source, Article.source_id == Source.id)
            .where(Article.story_id == story_id)
            .order_by(Article.published_at.asc().nulls_last(), Article.id.asc())
        ).all()
    )
    if not rows:
        session.delete(story)
        return
    _refresh(_Group(story=story, members=rows), now=datetime.now(timezone.utc))
