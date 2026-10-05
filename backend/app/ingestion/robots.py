"""Decide whether a public feed URL is allowed by robots.txt."""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

MAX_CRAWL_DELAY_SECONDS = 30


def robots_url_for(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def feed_is_allowed(robots_body: str | None, feed_url: str, user_agent: str) -> bool:
    """A missing robots file allows the fetch. An explicit rule can block it."""
    if robots_body is None:
        return True
    parser = RobotFileParser()
    parser.parse(robots_body.splitlines())
    return parser.can_fetch(user_agent, feed_url)


def crawl_delay_seconds(robots_body: str | None, user_agent: str) -> float:
    if not robots_body:
        return 0
    parser = RobotFileParser()
    parser.parse(robots_body.splitlines())
    delay = parser.crawl_delay(user_agent)
    if delay is None:
        return 0
    return min(float(delay), MAX_CRAWL_DELAY_SECONDS)
