"""Write the installable reader and the current feed as static files."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.schemas.feed import FeedArticleRead, FeedCategoryRead, FeedDetailRead
from app.services.feed_service import list_categories, list_feed

READER_DIR = Path(__file__).resolve().parents[1] / "reader"

PHONE_SW = """const CACHE = "ghanaed-phone-1";
const SHELL = [
  "./index.html",
  "./styles.css",
  "./app.js",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./data/feed.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(event.request);
        if (cached) return cached;
        if (event.request.mode === "navigate") {
          const page = await caches.match("./index.html");
          if (page) return page;
        }
        return Response.error();
      }),
  );
});
"""


class SnapshotRefused(Exception):
    """The folder already holds a usable feed, and this export would replace it with nothing."""


def publish_snapshot(session: Session, destination: Path) -> dict:
    """Write the phone site. An empty export does not erase a feed that already has stories."""
    catalog = build_catalog(session)
    previous = _story_count(destination)
    if previous and not catalog["stories"]:
        raise SnapshotRefused(f"Kept the last good copy ({previous} stories). This export had none.")

    destination.mkdir(parents=True, exist_ok=True)
    _write_shell(destination)
    data_dir = destination / "data"
    data_dir.mkdir(exist_ok=True)
    temporary = data_dir / "feed.json.tmp"
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(data_dir / "feed.json")
    return catalog


def build_catalog(session: Session) -> dict:
    stories = list_feed(session, limit=10000)
    categories = list_categories(session)
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "categories": [FeedCategoryRead(name=item.name, story_count=item.story_count).model_dump() for item in categories],
        "stories": [_story_payload(story) for story in stories],
    }


def _story_payload(story) -> dict:
    detail = FeedDetailRead(
        id=story.id,
        title=story.title,
        summary=story.summary,
        category=story.category,
        published_at=story.published_at,
        source_count=story.source_count,
        sources=story.sources,
        rank=story.rank,
        articles=[
            FeedArticleRead(
                source_name=source_name,
                title=article.title,
                url=article.url,
                published_at=article.published_at,
                excerpt=article.excerpt,
            )
            for article, source_name in story.articles
        ],
    )
    return detail.model_dump(mode="json")


def _story_count(destination: Path) -> int | None:
    path = destination / "data" / "feed.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    stories = payload.get("stories") if isinstance(payload, dict) else None
    if not isinstance(stories, list):
        return None
    return len(stories)


def _write_shell(destination: Path) -> None:
    html = (READER_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("/app/", "")
    html = html.replace('<html lang="en">', '<html lang="en" data-feed="static">', 1)
    (destination / "index.html").write_text(html, encoding="utf-8")
    for name in ("styles.css", "app.js", "icon-192.png", "icon-512.png"):
        shutil.copyfile(READER_DIR / name, destination / name)
    manifest = json.loads((READER_DIR / "manifest.webmanifest").read_text(encoding="utf-8"))
    manifest["start_url"] = "./"
    manifest["scope"] = "./"
    for icon in manifest["icons"]:
        icon["src"] = str(icon["src"]).removeprefix("/app/")
    (destination / "manifest.webmanifest").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (destination / "sw.js").write_text(PHONE_SW, encoding="utf-8")
    (destination / ".nojekyll").write_text("", encoding="utf-8")
