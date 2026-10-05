"""Runtime configuration loaded from the environment."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}


class Settings(BaseSettings):
    """Values that change between a laptop and a future hosted environment."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Ghana Education News"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/ghanaed.db"
    log_level: str = "INFO"
    ingestion_enabled: bool = True
    ingestion_interval_seconds: int = Field(default=300, ge=30, le=86400)
    ingestion_timeout_seconds: float = Field(default=20, gt=0, le=60)
    relevance_publish_threshold: float = Field(default=0.6, ge=0, le=1)
    relevance_reject_threshold: float = Field(default=0.35, ge=0, le=1)
    feed_rank_recency_weight: float = Field(default=0.55, ge=0, le=1)
    feed_rank_coverage_weight: float = Field(default=0.30, ge=0, le=1)
    feed_rank_relevance_weight: float = Field(default=0.15, ge=0, le=1)
    feed_recency_half_life_hours: float = Field(default=36, gt=0, le=24 * 30)

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in LOG_LEVELS:
            allowed = ", ".join(sorted(LOG_LEVELS))
            raise ValueError(f"LOG_LEVEL must be one of: {allowed}")
        return normalized

    @model_validator(mode="after")
    def relevance_thresholds_are_ordered(self) -> "Settings":
        if self.relevance_reject_threshold >= self.relevance_publish_threshold:
            raise ValueError("RELEVANCE_REJECT_THRESHOLD must be lower than RELEVANCE_PUBLISH_THRESHOLD")
        return self

    @model_validator(mode="after")
    def feed_rank_weights_sum_to_one(self) -> "Settings":
        total = self.feed_rank_recency_weight + self.feed_rank_coverage_weight + self.feed_rank_relevance_weight
        if abs(total - 1) > 0.001:
            raise ValueError("Feed rank weights must add up to 1")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def resolve_database_url(url: str) -> str:
    """Turn a relative SQLite URL into a file under the backend directory."""
    memory_urls = {"sqlite://", "sqlite:///:memory:"}
    if url in memory_urls or url.startswith("sqlite:///:memory:"):
        return url

    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url

    raw_path = url[len(prefix) :]
    path = Path(raw_path)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"
