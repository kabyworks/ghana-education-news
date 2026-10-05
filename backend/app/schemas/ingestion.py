"""Responses for ingestion runs and stored articles."""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_serializer


class SourceRunRead(BaseModel):
    source_id: int
    source_name: str
    status: str
    articles_discovered: int
    articles_stored: int
    duplicates_skipped: int
    entries_ignored: int
    duration_seconds: float
    error: str | None


class IngestionReportRead(BaseModel):
    sources_considered: int
    sources_succeeded: int
    sources_failed: int
    sources_skipped: int
    articles_discovered: int
    articles_stored: int
    duplicates_skipped: int
    results: list[SourceRunRead]


class ArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    source_name: str
    title: str
    url: str
    canonical_url: str
    author: str | None
    published_at: datetime | None
    discovered_at: datetime
    excerpt: str | None
    image_url: str | None
    processing_status: str
    ghana_relevance: float | None
    education_relevance: float | None
    relevance_score: float | None
    relevance_decision: str | None
    relevance_reason: str | None
    story_id: int | None
    content_hash: str

    @field_serializer("published_at", "discovered_at")
    def as_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
