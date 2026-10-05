"""Rule-based Ghana and education scores."""

import re
from dataclasses import dataclass

from app.core.config import get_settings
from app.intelligence.relevance.terms import EDUCATION_STRONG, EDUCATION_WEAK, GHANA_STRONG

DECISIONS = {"publish", "reject", "review"}
_REASON_LIMIT = 500


@dataclass(frozen=True)
class RelevanceResult:
    ghana_relevance: float
    education_relevance: float
    overall_relevance: float
    decision: str
    reason: str


def score_text(
    title: str,
    excerpt: str | None = None,
    *,
    publish_threshold: float | None = None,
    reject_threshold: float | None = None,
    source_covers_ghana: bool = False,
) -> RelevanceResult:
    settings = get_settings()
    publish_at = settings.relevance_publish_threshold if publish_threshold is None else publish_threshold
    reject_at = settings.relevance_reject_threshold if reject_threshold is None else reject_threshold
    ghana, ghana_terms = _dimension_score(title, excerpt or "", GHANA_STRONG, ())
    education, education_terms = _dimension_score(title, excerpt or "", EDUCATION_STRONG, EDUCATION_WEAK)
    if source_covers_ghana and ghana < 0.66:
        ghana = 0.66
        ghana_terms = [*ghana_terms, "Ghana source"]
    overall = round(min(ghana, education), 2)
    if ghana < reject_at or education < reject_at:
        decision = "reject"
    elif ghana >= publish_at and education >= publish_at:
        decision = "publish"
    else:
        decision = "review"
    return RelevanceResult(
        ghana_relevance=ghana,
        education_relevance=education,
        overall_relevance=overall,
        decision=decision,
        reason=_reason(ghana, ghana_terms, education, education_terms, overall, decision),
    )


def _dimension_score(title: str, body: str, strong: tuple[str, ...], weak: tuple[str, ...]) -> tuple[float, list[str]]:
    strong_title = _hits(title, strong)
    weak_title = [term for term in _hits(title, weak) if term not in strong_title]
    strong_body = [term for term in _hits(body, strong) if term not in strong_title]
    weak_body = [term for term in _hits(body, weak) if term not in strong_title and term not in weak_title and term not in strong_body]
    matched = strong_title + weak_title + strong_body + weak_body
    if not matched:
        return 0.0, []
    if strong_title:
        score = min(1.0, 0.78 + 0.06 * (len(strong_title) - 1))
    elif weak_title and strong_body:
        score = 0.7
    elif weak_title:
        score = 0.48
    elif len(strong_body) >= 2 or (strong_body and weak_body):
        score = 0.66
    elif strong_body:
        score = 0.5
    elif len(weak_body) >= 2:
        score = 0.4
    else:
        score = 0.28
    return round(score, 2), matched[:6]


def _hits(text: str, terms: tuple[str, ...]) -> list[str]:
    if not text:
        return []
    folded = text.casefold()
    found: list[str] = []
    for term in sorted(terms, key=len, reverse=True):
        needle = term.casefold()
        if " " in needle:
            matched = needle in folded
        else:
            matched = re.search(rf"\b{re.escape(needle)}\b", folded) is not None
        if matched and term not in found:
            found.append(term)
    return found


def _reason(
    ghana: float,
    ghana_terms: list[str],
    education: float,
    education_terms: list[str],
    overall: float,
    decision: str,
) -> str:
    ghana_text = ", ".join(ghana_terms) or "no terms"
    education_text = ", ".join(education_terms) or "no terms"
    text = (
        f"Ghana {ghana:.2f} ({ghana_text}). "
        f"Education {education:.2f} ({education_text}). "
        f"Overall {overall:.2f}. Decision: {decision}."
    )
    return text[:_REASON_LIMIT]
