"""A publisher or institution the pipeline is allowed to read from."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    base_url: Mapped[str] = mapped_column(String(500))
    feed_url: Mapped[str | None] = mapped_column(String(500), unique=True)
    source_type: Mapped[str] = mapped_column(String(50))
    trust_score: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    crawl_frequency_minutes: Mapped[int] = mapped_column(Integer)
    discovery_method: Mapped[str] = mapped_column(String(30))
    parser_key: Mapped[str] = mapped_column(String(50))
    fallback_method: Mapped[str | None] = mapped_column(String(30))
    requires_review: Mapped[bool] = mapped_column(Boolean, default=True)
    covers_ghana: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
