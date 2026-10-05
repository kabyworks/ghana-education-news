"""Initial publishers checked on 2026-10-05.

RSS addresses in this list returned an RSS document from this PC on that date.
Pages without a feed are registered so they can be enabled later, and no feed
URL is invented for them.
"""

from app.schemas.source import SourceCreate

_RAW_SOURCES: list[dict[str, object]] = [
    {
        "name": "MyJoyOnline Education",
        "base_url": "https://www.myjoyonline.com/",
        "feed_url": "https://www.myjoyonline.com/feed/",
        "source_type": "news",
        "trust_score": 0.7,
        "crawl_frequency_minutes": 180,
        "discovery_method": "rss",
        "parser_key": "generic_rss",
        "notes": (
            "General RSS returned application/rss+xml with entries on 2026-10-05. "
            "The education category address redirected to an empty comments feed, "
            "so relevance filtering has to drop non-education items later."
        ),
    },
    {
        "name": "Adom Online Education",
        "base_url": "https://www.adomonline.com/",
        "feed_url": "https://www.adomonline.com/category/education/feed/",
        "source_type": "news",
        "trust_score": 0.65,
        "crawl_frequency_minutes": 180,
        "discovery_method": "rss",
        "parser_key": "generic_rss",
        "notes": "Education category RSS returned application/rss+xml on 2026-10-05.",
    },
    {
        "name": "3News",
        "base_url": "https://3news.com/",
        "feed_url": "https://3news.com/feed/",
        "source_type": "news",
        "trust_score": 0.65,
        "crawl_frequency_minutes": 180,
        "discovery_method": "rss",
        "parser_key": "generic_rss",
        "notes": (
            "General news RSS returned application/rss+xml on 2026-10-05. "
            "The education category feed URL returned 404, so relevance filtering "
            "has to drop non-education items later."
        ),
    },
    {
        "name": "Ghana Tertiary Education Commission",
        "base_url": "https://gtec.edu.gh/",
        "feed_url": "https://gtec.edu.gh/feed/",
        "source_type": "government",
        "trust_score": 0.9,
        "crawl_frequency_minutes": 720,
        "discovery_method": "rss",
        "parser_key": "generic_rss",
        "notes": "Commission RSS returned application/rss+xml on 2026-10-05.",
    },
    {
        "name": "Graphic Online Education",
        "base_url": "https://www.graphic.com.gh/",
        "feed_url": None,
        "source_type": "news",
        "trust_score": 0.75,
        "crawl_frequency_minutes": 1440,
        "discovery_method": "html",
        "parser_key": "none",
        "notes": (
            "Education section https://www.graphic.com.gh/news/education.html "
            "returned HTML on 2026-10-05. https://www.graphic.com.gh/feed returned 404. "
            "No feed is stored until a public RSS or API address is confirmed."
        ),
    },
    {
        "name": "Ministry of Education",
        "base_url": "https://moe.gov.gh/",
        "feed_url": None,
        "source_type": "government",
        "trust_score": 0.9,
        "crawl_frequency_minutes": 1440,
        "discovery_method": "html",
        "parser_key": "none",
        "notes": (
            "Homepage returned HTML on 2026-10-05. /feed returned 404. "
            "No feed is stored until a public RSS or API address is confirmed."
        ),
    },
    {
        "name": "Ghana Education Service",
        "base_url": "https://ges.gov.gh/",
        "feed_url": None,
        "source_type": "government",
        "trust_score": 0.9,
        "crawl_frequency_minutes": 1440,
        "discovery_method": "html",
        "parser_key": "none",
        "notes": (
            "Official articles page is https://ges.gov.gh/articles.php. "
            "A direct request from this PC timed out on 2026-10-05, so no feed URL is stored."
        ),
    },
]


def initial_sources() -> list[SourceCreate]:
    return [SourceCreate.model_validate(item) for item in _RAW_SOURCES]
