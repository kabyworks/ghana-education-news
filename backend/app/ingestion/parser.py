"""Read RSS and Atom entries into plain article fields."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser

from app.ingestion.text import excerpt_from_html, html_to_text
from app.ingestion.urls import InvalidArticleUrlError, normalize_url

TITLE_LIMIT = 500
AUTHOR_LIMIT = 200
URL_LIMIT = 1000


class InvalidFeedError(Exception):
    """The response was not a usable feed."""


@dataclass(frozen=True)
class ParsedArticle:
    url: str
    canonical_url: str
    title: str
    author: str | None
    published_at: datetime | None
    excerpt: str | None
    image_url: str | None
    language: str | None


@dataclass(frozen=True)
class FeedDocument:
    articles: list[ParsedArticle]
    entries_ignored: int


def parse_feed(payload: bytes) -> FeedDocument:
    parsed = feedparser.parse(payload)
    if parsed.bozo and not parsed.entries:
        raise InvalidFeedError("Feed could not be parsed")
    language = _clean_language(parsed.feed.get("language"))
    articles: list[ParsedArticle] = []
    ignored = 0
    for entry in parsed.entries:
        article = _parse_entry(entry, language)
        if article is None:
            ignored += 1
        else:
            articles.append(article)
    return FeedDocument(articles=articles, entries_ignored=ignored)


def _parse_entry(entry: feedparser.FeedParserDict, language: str | None) -> ParsedArticle | None:
    link = entry.get("link")
    if not isinstance(link, str) or not link.strip():
        return None
    try:
        canonical_url = normalize_url(link)
    except InvalidArticleUrlError:
        return None
    if len(link.strip()) > URL_LIMIT or len(canonical_url) > URL_LIMIT:
        return None
    title = html_to_text(str(entry.get("title") or "")).strip() or "Untitled"
    author = _clean_author(entry.get("author"))
    return ParsedArticle(
        url=link.strip(),
        canonical_url=canonical_url,
        title=title[:TITLE_LIMIT],
        author=author,
        published_at=_published_at(entry),
        excerpt=excerpt_from_html(entry.get("summary") or entry.get("description")),
        image_url=_image_url(entry),
        language=language,
    )


def _published_at(entry: feedparser.FeedParserDict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def _clean_author(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()).strip()
    if not cleaned:
        return None
    return cleaned[:AUTHOR_LIMIT]


def _clean_language(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()[:16]
    return cleaned or None


def _image_url(entry: feedparser.FeedParserDict) -> str | None:
    for collection, key in (
        (entry.get("media_thumbnail"), "url"),
        (entry.get("media_content"), "url"),
        (entry.get("enclosures"), "href"),
    ):
        if not collection:
            continue
        for item in collection:
            if not isinstance(item, dict):
                continue
            if key == "href" and not str(item.get("type") or "").startswith("image/"):
                continue
            candidate = item.get(key) or item.get("url")
            if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                if len(candidate) <= URL_LIMIT:
                    return candidate
    return None


def og_image(html: str) -> str | None:
    """The picture a publisher names for the page, when the feed itself has none."""
    if not html:
        return None
    for pattern in (
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    ):
        match = re.search(pattern, html, re.IGNORECASE)
        if match is None:
            continue
        candidate = match.group(1).strip()
        if candidate.startswith(("http://", "https://")) and len(candidate) <= URL_LIMIT:
            return candidate
    return None
