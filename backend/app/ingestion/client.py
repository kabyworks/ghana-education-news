"""HTTP fetch for public feeds."""

import logging
import time
from typing import Protocol

import httpx2

from app import __version__
from app.ingestion.robots import crawl_delay_seconds, feed_is_allowed, robots_url_for

logger = logging.getLogger(__name__)

USER_AGENT = f"GhanaEducationNews/{__version__} (personal local education reader)"


class FeedClient(Protocol):
    def get_feed(self, url: str) -> bytes:
        """Return the raw feed body or raise if it cannot be read."""


class FeedNotAllowedError(Exception):
    """robots.txt disallows this feed, or the robots file itself was refused."""


class HttpxFeedClient:
    def __init__(self, timeout: float = 20, transport: httpx2.BaseTransport | None = None) -> None:
        self._timeout = timeout
        self._transport = transport
        self._robots: dict[str, str | None] = {}

    def get_feed(self, url: str) -> bytes:
        robots_body = self._robots_text(url)
        if not feed_is_allowed(robots_body, url, USER_AGENT):
            raise FeedNotAllowedError(f"robots.txt disallows {url}")
        delay = crawl_delay_seconds(robots_body, USER_AGENT)
        if delay > 0:
            time.sleep(delay)
        response = self._get(url)
        response.raise_for_status()
        return response.content

    def _robots_text(self, url: str) -> str | None:
        robots_url = robots_url_for(url)
        if robots_url in self._robots:
            return self._robots[robots_url]
        try:
            response = self._get(robots_url)
        except httpx2.HTTPError:
            logger.warning("Could not read robots.txt at %s", robots_url)
            self._robots[robots_url] = None
            return None
        if response.status_code == 404:
            body = None
        elif response.status_code in {401, 403}:
            raise FeedNotAllowedError(f"robots.txt refused access for {robots_url}")
        elif response.status_code >= 400:
            logger.warning("robots.txt at %s returned %s", robots_url, response.status_code)
            body = None
        else:
            body = response.text
        self._robots[robots_url] = body
        return body

    def _get(self, url: str) -> httpx2.Response:
        options: dict[str, object] = {
            "timeout": self._timeout,
            "follow_redirects": True,
            "headers": {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
        }
        if self._transport is not None:
            options["transport"] = self._transport
        with httpx2.Client(**options) as client:
            return client.get(url)
