"""Rank a story for the reader feed. Higher is more worth opening first."""

from datetime import datetime, timezone

COVERAGE_FULL_AT = 3


def rank_story(
    *,
    published_at: datetime | None,
    source_count: int,
    relevance: float,
    now: datetime,
    recency_weight: float = 0.55,
    coverage_weight: float = 0.30,
    relevance_weight: float = 0.15,
    half_life_hours: float = 36,
) -> float:
    recency = _recency(published_at, now=now, half_life_hours=half_life_hours)
    coverage = min(max(source_count, 0), COVERAGE_FULL_AT) / COVERAGE_FULL_AT
    relevance_score = min(max(relevance, 0.0), 1.0)
    score = recency_weight * recency + coverage_weight * coverage + relevance_weight * relevance_score
    return round(score, 4)


def _recency(published_at: datetime | None, *, now: datetime, half_life_hours: float) -> float:
    if published_at is None:
        return 0.0
    published = published_at if published_at.tzinfo is not None else published_at.replace(tzinfo=timezone.utc)
    current = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (current - published).total_seconds() / 3600)
    return 1 / (1 + age_hours / half_life_hours)
