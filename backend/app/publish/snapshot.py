"""Write the installable reader and the current feed as static files."""

import json
import re
import shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app.schemas.feed import FeedArticleRead, FeedCategoryRead, FeedDetailRead
from app.services.feed_service import list_categories, list_feed, story_image

READER_DIR = Path(__file__).resolve().parents[1] / "reader"

SITE = "https://edulens360.com"
SHELL_VERSION = "7"

PHONE_SW = """const CACHE = "ghanaed-phone-3";
const SHELL = [
  "./index.html",
  "./styles.css?v=7",
  "./app.js?v=7",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./logo.svg",
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
    fetch(new Request(event.request, { cache: "reload" }))
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
    _write_story_pages(destination, catalog["stories"])
    _write_discovery(destination, catalog)
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
        image_url=story_image(story.articles),
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
    payload = detail.model_dump(mode="json")
    payload["path"] = story_path(story.id, story.title)
    return payload


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
    for name in ("styles.css", "app.js", "icon-192.png", "icon-512.png", "logo.svg"):
        shutil.copyfile(READER_DIR / name, destination / name)
    manifest = json.loads((READER_DIR / "manifest.webmanifest").read_text(encoding="utf-8"))
    manifest["start_url"] = "./"
    manifest["scope"] = "./"
    for icon in manifest["icons"]:
        icon["src"] = str(icon["src"]).removeprefix("/app/")
    (destination / "manifest.webmanifest").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (destination / "sw.js").write_text(PHONE_SW, encoding="utf-8")
    (destination / ".nojekyll").write_text("", encoding="utf-8")


CATEGORY_LABELS = {
    "teachers": "Teachers",
    "higher_education": "University",
    "basic_schools": "Basic schools",
    "examinations": "Examinations",
    "scholarships": "Scholarships",
    "policy": "Policy",
    "general": "General",
}

HOME_MARKER = '<main id="main"><p class="notice">Loading stories…</p></main>'


def story_slug(title: str) -> str:
    folded = title.casefold().replace("'", "").replace("\u2019", "").replace("\u2018", "")
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    if len(slug) > 80:
        trimmed = slug[:80]
        slug = trimmed.rsplit("-", 1)[0] if "-" in trimmed else trimmed
    return slug.strip("-") or "story"


def story_path(story_id: int, title: str) -> str:
    return f"story/{story_id}/{story_slug(title)}/"


def _write_story_pages(destination: Path, stories: list[dict]) -> None:
    root = destination / "story"
    root.mkdir(exist_ok=True)
    keep = set()
    for story in stories:
        story_id = str(story["id"])
        keep.add(story_id)
        slug = story_slug(story["title"])
        folder = root / story_id
        folder.mkdir(exist_ok=True)
        for child in list(folder.iterdir()):
            if child.is_dir() and child.name != slug:
                shutil.rmtree(child)
            elif child.is_file() and child.name != "index.html":
                child.unlink()
        page = folder / slug / "index.html"
        page.parent.mkdir(exist_ok=True)
        page.write_text(_story_page(story), encoding="utf-8")
        (folder / "index.html").write_text(_story_redirect(story, slug), encoding="utf-8")
    for child in list(root.iterdir()):
        if child.is_dir() and child.name not in keep:
            shutil.rmtree(child)


def _write_discovery(destination: Path, catalog: dict) -> None:
    stories = catalog["stories"]
    index = destination / "index.html"
    page = index.read_text(encoding="utf-8")
    if HOME_MARKER not in page:
        raise RuntimeError("The phone homepage has no place to list stories.")
    items = "\n".join(
        f'    <li><a href="{escape(story["path"], quote=True)}">{escape(story["title"])}</a></li>'
        for story in stories
    )
    listing = (
        "<main id=\"main\">\n"
        "  <h1>Ghana education news</h1>\n"
        "  <ul class=\"story-index\">\n"
        f"{items}\n"
        "  </ul>\n"
        "</main>"
    )
    index.write_text(page.replace(HOME_MARKER, listing, 1), encoding="utf-8")
    updated = (catalog.get("generated_at") or "")[:10]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        "  <url>",
        f"    <loc>{SITE}/</loc>",
        f"    <lastmod>{escape(updated)}</lastmod>" if updated else "",
        "  </url>",
    ]
    for story in stories:
        published = str(story.get("published_at") or "")[:10]
        lines.extend(
            [
                "  <url>",
                f"    <loc>{SITE}/{escape(story['path'], quote=True)}</loc>",
                f"    <lastmod>{escape(published)}</lastmod>" if published else "",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    (destination / "sitemap.xml").write_text("\n".join(line for line in lines if line) + "\n", encoding="utf-8")
    (destination / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: https://edulens360.com/sitemap.xml\n",
        encoding="utf-8",
    )


def _story_redirect(story: dict, slug: str) -> str:
    title = escape(story["title"])
    target = escape(slug + "/", quote=True)
    canonical = escape(f"{SITE}/{story['path']}", quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url={target}">
  <link rel="canonical" href="{canonical}">
  <title>{title} · Edulens360</title>
</head>
<body>
  <p><a href="{target}">{title}</a></p>
</body>
</html>
"""


def _story_page(story: dict) -> str:
    title = escape(story["title"])
    summary = escape(story.get("summary") or "")
    canonical = escape(f"{SITE}/{story['path']}", quote=True)
    description = escape(_plain(story.get("summary") or "", 180), quote=True)
    label = escape(CATEGORY_LABELS.get(story.get("category") or "", "") or "Education")
    when = escape(_format_when(story.get("published_at")))
    count = int(story.get("source_count") or 0)
    sources = "1 source" if count == 1 else f"{count} sources"
    image = _http_url(story.get("image_url"))
    photo = ""
    if image:
        photo = f'<img class="card-photo" alt="" src="{escape(image, quote=True)}" referrerpolicy="no-referrer">'
    blocks = "\n".join(_source_block(article) for article in _public_articles(story))
    data = json.dumps(_saved_copy(story), ensure_ascii=False).replace("<", "\\u003c")
    image_meta = f'<meta property="og:image" content="{escape(image, quote=True)}">' if image else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#1c3d2e">
  <title>{title} · Edulens360</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="article">
  {image_meta}
  <meta name="twitter:card" content="summary">
  <link rel="icon" href="../../../icon-192.png">
  <link rel="stylesheet" href="../../../styles.css?v={SHELL_VERSION}">
  <script type="application/ld+json">
    {json.dumps(_article_schema(story, image), ensure_ascii=False).replace("<", "\\u003c")}
  </script>
</head>
<body>
  <header>
    <div class="bar">
      <a class="brand" href="../../../"><img src="../../../logo.svg" alt="Edulens360" width="64" height="56"></a>
    </div>
    <form id="search" role="search" action="../../../" method="get">
      <input id="search-input" type="search" name="q" placeholder="Search headlines" enterkeyhint="search" aria-label="Search headlines">
      <button type="submit">
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">
          <circle cx="10.5" cy="10.5" r="6.25" fill="none" stroke="currentColor" stroke-width="2"></circle>
          <path d="M15.2 15.2L20.5 20.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path>
        </svg>
        Search
      </button>
    </form>
  </header>
  <main id="main">
    <article class="story">
      <a class="back" href="../../../" aria-label="Back to latest">Back</a>
      <p class="kicker">{label} · {when} · {sources}</p>
      <div class="headline"><h1>{title}</h1>{photo}</div>
      <p class="summary">{summary}</p>
      <div class="actions"><button type="button" id="save-story">Save</button></div>
      {blocks}
    </article>
  </main>
  <script type="application/json" id="story-data">{data}</script>
  <script>
    const story = JSON.parse(document.getElementById("story-data").textContent);
    const button = document.getElementById("save-story");
    const key = "ghanaed.saved.v1";
    function readSaved() {{
      try {{
        const parsed = JSON.parse(localStorage.getItem(key) || "[]");
        return Array.isArray(parsed) ? parsed : [];
      }} catch (error) {{
        return [];
      }}
    }}
    function paintSaved() {{
      const on = readSaved().some((item) => item.id === story.id);
      button.textContent = on ? "Remove save" : "Save";
      button.classList.toggle("secondary", on);
    }}
    button.addEventListener("click", () => {{
      const current = readSaved();
      const next = current.some((item) => item.id === story.id)
        ? current.filter((item) => item.id !== story.id)
        : [story, ...current];
      localStorage.setItem(key, JSON.stringify(next));
      paintSaved();
    }});
    paintSaved();
  </script>
</body>
</html>
"""


def _public_articles(story: dict) -> list[dict]:
    """One original link per publisher, so a story page stays a summary rather than a pile of posts."""
    chosen: dict[str, dict] = {}
    for article in story.get("articles") or []:
        name = article.get("source_name") or "Source"
        current = chosen.get(name)
        if current is None or (article.get("published_at") or "") > (current.get("published_at") or ""):
            chosen[name] = article
    ordered = [chosen[name] for name in story.get("sources") or [] if name in chosen]
    for article in chosen.values():
        if article not in ordered:
            ordered.append(article)
    return ordered


def _source_block(article: dict) -> str:
    name = escape(article.get("source_name") or "Source")
    excerpt = escape(article.get("excerpt") or "")
    url = escape(article.get("url") or "", quote=True)
    text = f"<p class=\"summary\">{excerpt}</p>" if excerpt else ""
    return (
        "<section class=\"source\">"
        f"<h3>{name}</h3>"
        f"{text}"
        f'<a class="link-button secondary" href="{url}" target="_blank" rel="noreferrer">Read at {name}</a>'
        "</section>"
    )


def _article_schema(story: dict, image: str) -> dict:
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": story["title"],
        "description": _plain(story.get("summary") or "", 180),
        "datePublished": story.get("published_at"),
        "mainEntityOfPage": f"{SITE}/{story['path']}",
        "publisher": {"@type": "Organization", "name": "Edulens360", "url": SITE + "/"},
    }
    if image:
        schema["image"] = image
    return schema


def _saved_copy(story: dict) -> dict:
    return {
        "id": story["id"],
        "title": story["title"],
        "summary": story.get("summary") or "",
        "category": story.get("category"),
        "published_at": story.get("published_at"),
        "source_count": story.get("source_count"),
        "sources": story.get("sources") or [],
        "image_url": story.get("image_url"),
        "path": story.get("path") or "",
        "articles": story.get("articles") or [],
    }


def _plain(value: str, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    trimmed = text[: limit - 1].rsplit(" ", 1)[0]
    return (trimmed or text[: limit - 1]).rstrip() + "…"


def _format_when(value: str | None) -> str:
    if not value:
        return ""
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return f"{when.day} {when.strftime('%b')} {when.year}"


def _http_url(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not (text.startswith("https://") or text.startswith("http://")):
        return ""
    parts = urlsplit(text)
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%"), parts.query, ""))
