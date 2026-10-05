"""A group of articles about the same event."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.models.source import utcnow


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), index=True)
    article_count: Mapped[int] = mapped_column(Integer, default=1)
    first_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reader_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    editor_title: Mapped[str | None] = mapped_column(String(500))
    editor_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
