"""Turn feed links into a stable identity for duplicate detection."""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
}


class InvalidArticleUrlError(ValueError):
    """The link is not an http or https URL."""


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidArticleUrlError("Article URL must start with http:// or https://")
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    query.sort()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    netloc = parsed.netloc.lower()
    if parsed.scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    if parsed.scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    return urlunparse((parsed.scheme.lower(), netloc, path, "", urlencode(query), ""))
