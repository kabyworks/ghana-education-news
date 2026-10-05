"""Reader-facing feed responses. These omit stored article bodies."""

from datetime import datetime, timezone

from pydantic import BaseModel, field_serializer


class FeedStoryRead(BaseModel):
    id: int
    title: str
    summary: str
    category: str
    published_at: datetime | None
    source_count: int
    sources: list[str]
    rank: float

    @field_serializer("published_at")
    def as_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class FeedArticleRead(BaseModel):
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


class FeedDetailRead(FeedStoryRead):
    articles: list[FeedArticleRead]


class FeedCategoryRead(BaseModel):
    name: str
    story_count: int
