"""Decide whether two articles describe the same event."""

import re
from datetime import datetime, timedelta, timezone

TITLE_WINDOW = timedelta(days=7)
EVENT_WINDOW = timedelta(days=14)
TITLE_SIMILARITY = 0.55

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "our",
        "over",
        "said",
        "says",
        "that",
        "the",
        "their",
        "this",
        "to",
        "we",
        "while",
        "will",
        "with",
    }
)
_STRIKE_TERMS = frozenset({"strike", "strikes", "striking"})
_TEACHER_TERMS = frozenset({"teacher", "teachers", "gnat", "nagrat", "pretag", "tewu", "union", "unions"})


def same_story(left, right) -> bool:
    gap = abs(_when(left) - _when(right))
    if gap <= TITLE_WINDOW and _jaccard(_tokens(left.title), _tokens(right.title)) >= TITLE_SIMILARITY:
        return True
    return gap <= EVENT_WINDOW and _is_teacher_strike(left.title) and _is_teacher_strike(right.title)


def representative_title(items: list[tuple[str, float]]) -> str:
    """Pick the title that reads most like the rest of the group. Higher trust wins a tie."""
    pool = [item for item in items if _is_teacher_strike(item[0])] or items
    ordered = sorted(pool, key=lambda item: item[1], reverse=True)
    if len(ordered) == 1:
        return ordered[0][0]
    token_sets = [_tokens(title) for title, _trust in ordered]
    best_title = ordered[0][0]
    best_score = -1.0
    for index, (title, _trust) in enumerate(ordered):
        others = token_sets[:index] + token_sets[index + 1 :]
        score = sum(_jaccard(token_sets[index], other) for other in others) / len(others)
        if score > best_score:
            best_title = title
            best_score = score
    return best_title


def _is_teacher_strike(title: str) -> bool:
    words = _words(title)
    return bool(words & _STRIKE_TERMS) and bool(words & _TEACHER_TERMS)


def _tokens(text: str) -> set[str]:
    return {word for word in _words(text) if len(word) >= 3 and word not in _STOPWORDS}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _when(article) -> datetime:
    value = article.published_at or article.discovered_at
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
