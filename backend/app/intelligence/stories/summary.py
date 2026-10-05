"""First sentences of a stored excerpt. This does not fetch or invent article text."""

import re

SUMMARY_LIMIT = 320


def extractive_summary(text: str, *, limit: int = SUMMARY_LIMIT) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    chosen: list[str] = []
    total = 0
    for sentence in sentences:
        extra = len(sentence) if not chosen else len(sentence) + 1
        if chosen and total + extra > limit:
            break
        chosen.append(sentence)
        total += extra
        if len(chosen) == 2:
            break
    summary = " ".join(chosen) if chosen else cleaned
    if len(summary) > limit:
        summary = summary[: limit - 3].rstrip() + "..."
    return summary
