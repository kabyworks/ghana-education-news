"""Fetch due RSS sources and store articles that have not been seen."""

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.article import Article
from app.db.models.source import Source
from app.ingestion.parser import og_image, parse_feed
from app.intelligence.relevance.service import apply_relevance
from app.intelligence.stories.service import build_stories
from app.services.source_service import record_source_check

logger = logging.getLogger(__name__)

_run_lock = threading.Lock()


class IngestionBusyError(Exception):
    """Another ingestion run is still in progress."""


@dataclass
class SourceRunResult:
    source_id: int
    source_name: str
    status: str
    articles_discovered: int = 0
    articles_stored: int = 0
    duplicates_skipped: int = 0
    entries_ignored: int = 0
    duration_seconds: float = 0
    error: str | None = None


@dataclass
class IngestionReport:
    sources_considered: int
    sources_succeeded: int
    sources_failed: int
    sources_skipped: int
    articles_discovered: int
    articles_stored: int
    duplicates_skipped: int
    results: list[SourceRunResult]


@dataclass(frozen=True)
class _Target:
    id: int
    name: str
    active: bool
    feed_url: str | None
    discovery_method: str
    parser_key: str
    last_checked_at: datetime | None
    crawl_frequency_minutes: int


def run_ingestion(session: Session, client, *, force: bool = False) -> IngestionReport:
    if not _run_lock.acquire(blocking=False):
        raise IngestionBusyError
    try:
        return _run_ingestion(session, client, force=force)
    finally:
        _run_lock.release()


def _run_ingestion(session: Session, client, *, force: bool) -> IngestionReport:
    now = datetime.now(timezone.utc)
    targets = [_target_from(source) for source in session.scalars(select(Source).order_by(Source.id))]
    results: list[SourceRunResult] = []
    for target in targets:
        results.append(_process_target(session, client, target, now=now, force=force))
    report = IngestionReport(
        sources_considered=len(results),
        sources_succeeded=sum(1 for item in results if item.status == "succeeded"),
        sources_failed=sum(1 for item in results if item.status == "failed"),
        sources_skipped=sum(1 for item in results if item.status == "skipped"),
        articles_discovered=sum(item.articles_discovered for item in results),
        articles_stored=sum(item.articles_stored for item in results),
        duplicates_skipped=sum(item.duplicates_skipped for item in results),
        results=results,
    )
    logger.info(
        "Ingestion finished stored=%s duplicates=%s failed=%s skipped=%s",
        report.articles_stored,
        report.duplicates_skipped,
        report.sources_failed,
        report.sources_skipped,
    )
    build_stories(session)
    return report


def _process_target(session: Session, client, target: _Target, *, now: datetime, force: bool) -> SourceRunResult:
    reason = _skip_reason(target, now=now, force=force)
    if reason is not None:
        logger.debug("Skipped source %s (%s): %s", target.id, target.name, reason)
        return SourceRunResult(source_id=target.id, source_name=target.name, status="skipped", error=reason)

    started = time.perf_counter()
    assert target.feed_url is not None
    try:
        payload = client.get_feed(target.feed_url)
        document = parse_feed(payload)
        articles = [_with_page_image(client, article) for article in document.articles]
        stored, duplicates = _store_articles(session, target.id, articles, discovered_at=now)
        record_source_check(session, target.id, success=True)
    except Exception as exc:
        session.rollback()
        message = f"{type(exc).__name__}: {exc}"[:500]
        logger.exception("Source %s (%s) fetch failed", target.id, target.name)
        record_source_check(session, target.id, success=False, error=message)
        return SourceRunResult(
            source_id=target.id,
            source_name=target.name,
            status="failed",
            duration_seconds=round(time.perf_counter() - started, 2),
            error=message,
        )

    duration = round(time.perf_counter() - started, 2)
    logger.info(
        "Source %s (%s) stored %s articles, skipped %s duplicates, in %ss",
        target.id,
        target.name,
        stored,
        duplicates,
        duration,
    )
    return SourceRunResult(
        source_id=target.id,
        source_name=target.name,
        status="succeeded",
        articles_discovered=len(document.articles),
        articles_stored=stored,
        duplicates_skipped=duplicates,
        entries_ignored=document.entries_ignored,
        duration_seconds=duration,
    )


def _with_page_image(client, article):
    if article.image_url or not hasattr(client, "get_page"):
        return article
    try:
        html = client.get_page(article.url)
    except Exception:
        logger.info("Could not read a picture from %s", article.url)
        return article
    found = og_image(html or "")
    if not found:
        return article
    return replace(article, image_url=found)


def _store_articles(session: Session, source_id: int, articles, *, discovered_at: datetime) -> tuple[int, int]:
    stored = 0
    duplicates = 0
    seen: set[str] = set()
    for article in articles:
        if article.canonical_url in seen or _canonical_exists(session, article.canonical_url):
            duplicates += 1
            continue
        seen.add(article.canonical_url)
        now = datetime.now(timezone.utc)
        record = Article(
            source_id=source_id,
            url=article.url,
            canonical_url=article.canonical_url,
            title=article.title,
            author=article.author,
            published_at=article.published_at,
            discovered_at=discovered_at,
            excerpt=article.excerpt,
            image_url=article.image_url,
            content_hash=_content_hash(article.canonical_url, article.title, article.excerpt or ""),
            language=article.language,
            created_at=now,
            updated_at=now,
        )
        apply_relevance(record, session)
        session.add(record)
        stored += 1
    return stored, duplicates


def _canonical_exists(session: Session, canonical_url: str) -> bool:
    return session.scalar(select(Article.id).where(Article.canonical_url == canonical_url)) is not None


def _content_hash(canonical_url: str, title: str, excerpt: str) -> str:
    payload = "\n".join((canonical_url, title.casefold(), excerpt))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _target_from(source: Source) -> _Target:
    last_checked = source.last_checked_at
    if last_checked is not None and last_checked.tzinfo is None:
        last_checked = last_checked.replace(tzinfo=timezone.utc)
    return _Target(
        id=source.id,
        name=source.name,
        active=source.active,
        feed_url=source.feed_url,
        discovery_method=source.discovery_method,
        parser_key=source.parser_key,
        last_checked_at=last_checked,
        crawl_frequency_minutes=source.crawl_frequency_minutes,
    )


def _skip_reason(target: _Target, *, now: datetime, force: bool) -> str | None:
    if not target.active:
        return "inactive"
    if target.discovery_method != "rss" or target.parser_key != "generic_rss" or not target.feed_url:
        return "no rss feed"
    if force or target.last_checked_at is None:
        return None
    due_at = target.last_checked_at + timedelta(minutes=target.crawl_frequency_minutes)
    if now < due_at:
        return "not due"
    return None
