"""Create Edulens360 original posts that sit in the same reader feed as news."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.article import (
    PROCESSING_PUBLISHED,
    Article,
)
from app.db.models.source import Source
from app.db.models.story import Story

ORIGINAL_SOURCE_NAME = "Edulens360"
ORIGINAL_SOURCE_BASE = "https://edulens360.com/"


def ensure_original_source(session: Session) -> Source:
    source = session.scalar(select(Source).where(Source.name == ORIGINAL_SOURCE_NAME))
    if source is not None:
        return source
    now = datetime.now(timezone.utc)
    source = Source(
        name=ORIGINAL_SOURCE_NAME,
        base_url=ORIGINAL_SOURCE_BASE,
        feed_url=None,
        source_type="publication",
        trust_score=1.0,
        active=False,
        crawl_frequency_minutes=10080,
        discovery_method="manual",
        parser_key="none",
        fallback_method=None,
        requires_review=False,
        covers_ghana=True,
        notes="Original Edulens360 tips and guidance posts.",
        created_at=now,
        updated_at=now,
    )
    session.add(source)
    session.flush()
    return source


def create_original_post(
    session: Session,
    *,
    title: str,
    summary: str,
    body: str,
    category: str = "general",
    published_at: datetime | None = None,
) -> Story:
    """Insert one original tip as a visible story with a short card summary and full body."""
    clean_title = _one_line(title, 500)
    clean_summary = _one_line(summary, 500)
    clean_body = body.strip()
    if not clean_title:
        raise ValueError("title is required")
    if not clean_summary:
        raise ValueError("summary is required")
    if not clean_body:
        raise ValueError("body is required")
    if "\u2014" in clean_title or "\u2014" in clean_summary or "\u2014" in clean_body:
        raise ValueError("original posts must not use em dashes")

    source = ensure_original_source(session)
    now = published_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    story = Story(
        title=clean_title,
        summary=clean_summary,
        category=category,
        article_count=1,
        first_published_at=now,
        reader_visible=True,
        editor_title=clean_title,
        editor_summary=clean_summary,
        created_at=now,
        updated_at=now,
    )
    session.add(story)
    session.flush()

    canonical = f"{ORIGINAL_SOURCE_BASE}{_story_path(story.id, clean_title)}"
    article = Article(
        source_id=source.id,
        url=canonical,
        canonical_url=canonical,
        title=clean_title,
        author=ORIGINAL_SOURCE_NAME,
        published_at=now,
        discovered_at=now,
        excerpt=clean_body,
        image_url=None,
        content_hash=_content_hash(canonical, clean_title, clean_body),
        language="en",
        processing_status=PROCESSING_PUBLISHED,
        ghana_relevance=1.0,
        education_relevance=1.0,
        relevance_score=1.0,
        relevance_decision="publish",
        relevance_reason="original Edulens360 post",
        story_id=story.id,
        created_at=now,
        updated_at=now,
    )
    session.add(article)
    session.commit()
    session.refresh(story)
    return story


def is_original_source_name(name: str | None) -> bool:
    return (name or "").strip() == ORIGINAL_SOURCE_NAME


def format_tip_body_html(body: str) -> str:
    """Turn plain tip text into escaped HTML blocks. No raw HTML from the author."""
    from html import escape

    blocks: list[str] = []
    for raw in body.replace("\r\n", "\n").split("\n\n"):
        block = raw.strip()
        if not block:
            continue
        if block.startswith("### "):
            blocks.append(f"<h3>{escape(block[4:].strip())}</h3>")
            continue
        lines = [escape(line) for line in block.split("\n")]
        blocks.append(f'<p class="summary">{("<br>".join(lines))}</p>')
    return "\n".join(blocks)


def _one_line(value: str, limit: int) -> str:
    return " ".join(value.split())[:limit].strip()


def _story_path(story_id: int, title: str) -> str:
    folded = title.casefold().replace("'", "").replace("\u2019", "").replace("\u2018", "")
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    if len(slug) > 80:
        trimmed = slug[:80]
        slug = trimmed.rsplit("-", 1)[0] if "-" in trimmed else trimmed
    slug = slug.strip("-") or "story"
    return f"story/{story_id}/{slug}/"


def _content_hash(canonical_url: str, title: str, excerpt: str) -> str:
    payload = f"{canonical_url}\n{title}\n{excerpt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
