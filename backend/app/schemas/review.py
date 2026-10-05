"""Review desk responses."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer


class ReviewArticleRead(BaseModel):
    id: int
    title: str
    source_name: str
    url: str
    excerpt: str | None
    published_at: datetime | None

    @field_serializer("published_at")
    def as_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class ReviewStoryRead(BaseModel):
    id: int
    title: str
    generated_title: str
    summary: str
    generated_summary: str
    category: str
    article_count: int
    reader_visible: bool
    title_edited: bool
    summary_edited: bool


class StoryEdit(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    summary: str | None = Field(default=None, max_length=1000)
