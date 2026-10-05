"""Responses for grouped stories."""

from datetime import datetime, timezone

from pydantic import BaseModel, field_serializer


class StoryArticleRead(BaseModel):
    id: int
    source_name: str
    title: str
    url: str
    published_at: datetime | None
    excerpt: str | None

    @field_serializer("published_at")
    def as_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class StoryRead(BaseModel):
    id: int
    title: str
    summary: str
    category: str
    article_count: int
    first_published_at: datetime | None

    @field_serializer("first_published_at")
    def as_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class StoryDetailRead(StoryRead):
    articles: list[StoryArticleRead]


class StoryBuildRead(BaseModel):
    considered: int
    created: int
    attached: int
    stories: int
