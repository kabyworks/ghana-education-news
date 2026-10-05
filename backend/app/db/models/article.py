"""An article discovered from a source feed."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.models.source import utcnow

PROCESSING_NEW = "new"
PROCESSING_PUBLISHED = "published"
PROCESSING_REJECTED = "rejected"
PROCESSING_REVIEW = "review"


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    canonical_url: Mapped[str] = mapped_column(String(1000), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    excerpt: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1000))
    content_hash: Mapped[str] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(16))
    processing_status: Mapped[str] = mapped_column(String(32), default=PROCESSING_NEW)
    ghana_relevance: Mapped[float | None] = mapped_column(Float)
    education_relevance: Mapped[float | None] = mapped_column(Float)
    relevance_score: Mapped[float | None] = mapped_column(Float)
    relevance_decision: Mapped[str | None] = mapped_column(String(16), index=True)
    relevance_reason: Mapped[str | None] = mapped_column(Text)
    story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
