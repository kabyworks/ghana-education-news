"""Request and response models for the source registry."""

from datetime import datetime, timezone
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.sources.constants import DISCOVERY_METHODS, PARSER_KEYS, SOURCE_TYPES


def _clean_http_url(value: str) -> str:
    cleaned = value.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must start with http:// or https://")
    if parsed.username or parsed.password:
        raise ValueError("URL must not include a username or password")
    return cleaned


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


class SourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    base_url: str = Field(max_length=500)
    feed_url: str | None = Field(default=None, max_length=500)
    source_type: str
    trust_score: float = Field(default=0.5, ge=0, le=1)
    active: bool = True
    crawl_frequency_minutes: int = Field(ge=15, le=10080)
    discovery_method: str
    parser_key: str | None = None
    fallback_method: str | None = None
    requires_review: bool = True
    covers_ghana: bool = True
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Name must be at least 2 characters")
        return cleaned

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return _clean_http_url(value)

    @field_validator("feed_url", "notes", "fallback_method", mode="before")
    @classmethod
    def empty_optional_to_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("feed_url")
    @classmethod
    def validate_feed_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_http_url(value)

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        if value not in SOURCE_TYPES:
            allowed = ", ".join(sorted(SOURCE_TYPES))
            raise ValueError(f"source_type must be one of: {allowed}")
        return value

    @field_validator("discovery_method", "fallback_method")
    @classmethod
    def validate_discovery_method(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in DISCOVERY_METHODS:
            allowed = ", ".join(sorted(DISCOVERY_METHODS))
            raise ValueError(f"discovery method must be one of: {allowed}")
        return value

    @field_validator("parser_key")
    @classmethod
    def validate_parser_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in PARSER_KEYS:
            allowed = ", ".join(sorted(PARSER_KEYS))
            raise ValueError(f"parser_key must be one of: {allowed}")
        return value

    @model_validator(mode="after")
    def discovery_matches_feed(self) -> "SourceCreate":
        if self.discovery_method == "rss":
            if not self.feed_url:
                raise ValueError("An RSS source needs a feed URL")
            if self.parser_key is None:
                self.parser_key = "generic_rss"
            if self.parser_key != "generic_rss":
                raise ValueError("RSS sources use the generic_rss parser")
        else:
            if self.feed_url:
                raise ValueError("A feed URL is only valid when discovery is rss")
            if self.parser_key is None:
                self.parser_key = "none"
            if self.parser_key != "none":
                raise ValueError("Sources without an RSS feed use parser_key none")
        return self


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    base_url: str | None = Field(default=None, max_length=500)
    feed_url: str | None = Field(default=None, max_length=500)
    source_type: str | None = None
    trust_score: float | None = Field(default=None, ge=0, le=1)
    active: bool | None = None
    crawl_frequency_minutes: int | None = Field(default=None, ge=15, le=10080)
    discovery_method: str | None = None
    parser_key: str | None = None
    fallback_method: str | None = None
    requires_review: bool | None = None
    covers_ghana: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Name must be at least 2 characters")
        return cleaned

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_http_url(value)

    @field_validator("feed_url", "notes", "fallback_method", mode="before")
    @classmethod
    def empty_optional_to_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("feed_url")
    @classmethod
    def validate_feed_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_http_url(value)

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in SOURCE_TYPES:
            allowed = ", ".join(sorted(SOURCE_TYPES))
            raise ValueError(f"source_type must be one of: {allowed}")
        return value

    @field_validator("discovery_method", "fallback_method")
    @classmethod
    def validate_discovery_method(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in DISCOVERY_METHODS:
            allowed = ", ".join(sorted(DISCOVERY_METHODS))
            raise ValueError(f"discovery method must be one of: {allowed}")
        return value

    @field_validator("parser_key")
    @classmethod
    def validate_parser_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in PARSER_KEYS:
            allowed = ", ".join(sorted(PARSER_KEYS))
            raise ValueError(f"parser_key must be one of: {allowed}")
        return value


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    feed_url: str | None
    source_type: str
    trust_score: float
    active: bool
    crawl_frequency_minutes: int
    discovery_method: str
    parser_key: str
    fallback_method: str | None
    requires_review: bool
    covers_ghana: bool
    notes: str | None
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        "last_checked_at",
        "last_success_at",
        "created_at",
        "updated_at",
    )
    def as_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
