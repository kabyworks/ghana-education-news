"""Create, update, and record health for sources."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.source import Source
from app.schemas.source import SourceCreate, SourceUpdate
from app.sources.catalog import initial_sources

logger = logging.getLogger(__name__)

_ERROR_LIMIT = 500


class SourceNotFoundError(Exception):
    """The requested source id is not in the registry."""


class DuplicateSourceError(Exception):
    """A unique source field is already in use."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class InvalidSourceError(Exception):
    """The source record would break the registry rules."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class SourceInUseError(Exception):
    """The source cannot be removed while articles still point at it."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def list_sources(session: Session, *, active: bool | None = None) -> list[Source]:
    statement = select(Source).order_by(Source.name)
    if active is not None:
        statement = statement.where(Source.active == active)
    return list(session.scalars(statement))


def get_source(session: Session, source_id: int) -> Source:
    source = session.get(Source, source_id)
    if source is None:
        raise SourceNotFoundError
    return source


def create_source(session: Session, data: SourceCreate) -> Source:
    now = datetime.now(timezone.utc)
    source = Source(
        name=data.name,
        base_url=data.base_url,
        feed_url=data.feed_url,
        source_type=data.source_type,
        trust_score=data.trust_score,
        active=data.active,
        crawl_frequency_minutes=data.crawl_frequency_minutes,
        discovery_method=data.discovery_method,
        parser_key=data.parser_key or "none",
        fallback_method=data.fallback_method,
        requires_review=data.requires_review,
        covers_ghana=data.covers_ghana,
        notes=data.notes,
        created_at=now,
        updated_at=now,
    )
    _ensure_consistent(source)
    session.add(source)
    _commit(session, source)
    logger.info("Created source %s (%s)", source.id, source.name)
    return source


def update_source(session: Session, source_id: int, data: SourceUpdate) -> Source:
    source = get_source(session, source_id)
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(source, field, value)
    try:
        _ensure_consistent(source)
    except InvalidSourceError:
        session.rollback()
        raise
    source.updated_at = datetime.now(timezone.utc)
    _commit(session, source)
    logger.info("Updated source %s active=%s", source.id, source.active)
    return source


def delete_source(session: Session, source_id: int) -> None:
    source = get_source(session, source_id)
    name = source.name
    session.delete(source)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise SourceInUseError("This source still has articles") from exc
    logger.info("Deleted source %s (%s)", source_id, name)


def record_source_check(
    session: Session,
    source_id: int,
    *,
    success: bool,
    error: str | None = None,
) -> Source:
    """Store the outcome of a future fetch. Callers cannot set this through the API."""
    source = get_source(session, source_id)
    if not success and (error is None or not error.strip()):
        raise InvalidSourceError("A failed check needs an error message")
    now = datetime.now(timezone.utc)
    source.last_checked_at = now
    source.updated_at = now
    if success:
        source.last_success_at = now
        source.last_error = None
    else:
        source.last_error = str(error).strip()[:_ERROR_LIMIT]
    session.commit()
    session.refresh(source)
    if success:
        logger.info("Source %s check succeeded", source.id)
    else:
        logger.warning("Source %s check failed", source.id)
    return source


def seed_sources(session: Session) -> int:
    """Insert catalog sources that are not already stored. Existing rows are left as edited."""
    existing_names = set(session.scalars(select(Source.name)))
    added = 0
    for item in initial_sources():
        if item.name in existing_names:
            continue
        create_source(session, item)
        existing_names.add(item.name)
        added += 1
    return added


def _ensure_consistent(source: Source) -> None:
    if source.discovery_method == "rss":
        if not source.feed_url:
            raise InvalidSourceError("An RSS source needs a feed URL")
        if source.parser_key != "generic_rss":
            raise InvalidSourceError("RSS sources use the generic_rss parser")
        return
    if source.feed_url:
        raise InvalidSourceError("A feed URL is only valid when discovery is rss")
    if source.parser_key != "none":
        raise InvalidSourceError("Sources without an RSS feed use parser_key none")


def _commit(session: Session, source: Source) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        message = str(exc.orig).lower()
        if "feed_url" in message:
            raise DuplicateSourceError("A source with this feed URL already exists") from exc
        raise DuplicateSourceError("A source with this name already exists") from exc
    session.refresh(source)
