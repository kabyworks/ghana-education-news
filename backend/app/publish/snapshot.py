"""Write the installable reader and the current feed as static files."""

import json
import os
import re
import shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app.schemas.feed import FeedArticleRead, FeedCategoryRead, FeedDetailRead
from app.services.feed_service import list_categories, list_feed, story_image
from app.services.original_post import (
    blog_path,
    format_tip_body_html,
    is_original_source_name,
    tip_body_without_related,
    tip_lead,
)

READER_DIR = Path(__file__).resolve().parents[1] / "reader"

SITE = "https://edulens360.com"
SHELL_VERSION = "15"

PHONE_SW = """const CACHE = "ghanaed-phone-11";
const SHELL = [
  "./index.html",
  "./styles.css?v=15",
  "./app.js?v=15",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./logo.svg",
  "./privacy/",
];

function isFeedData(url) {
  return url.pathname.endsWith("/data/feed.json") || url.pathname.endsWith("/data/notify.json");
}

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
  event.respondWith((async () => {
    const cached = await caches.match(event.request);
    const fetching = fetch(event.request)
      .then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => undefined);

    // Feed data must stay fresh so new Edulens tips do not vanish behind an old cache.
    if (isFeedData(url)) {
      const network = await fetching;
      if (network) return network;
      if (cached) return cached;
      return Response.error();
    }

    if (cached) {
      fetching.catch(() => {});
      return cached;
    }
    const network = await fetching;
    if (network) return network;
    if (event.request.mode === "navigate") {
      const page = await caches.match("./index.html");
      if (page) return page;
    }
    return Response.error();
  })());
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
    originals = [story for story in catalog["stories"] if _is_original_story(story)]
    _attach_blog_urls(catalog["stories"])
    _write_story_pages(destination, catalog["stories"])
    _write_blog_pages(destination, originals)
    _write_discovery(destination, catalog, originals)
    data_dir = destination / "data"
    data_dir.mkdir(exist_ok=True)
    temporary = data_dir / "feed.json.tmp"
    _write_text(temporary, json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(data_dir / "feed.json")
    _write_notify(data_dir, catalog)
    return catalog


def _write_notify(data_dir: Path, catalog: dict) -> None:
    """Small file the Android app polls for new-story alerts."""
    stories = catalog.get("stories") or []
    latest = stories[0] if stories else None
    payload = {
        "updated_at": catalog.get("generated_at"),
        "latest": None
        if latest is None
        else {
            "id": latest["id"],
            "title": latest["title"],
            "path": latest.get("path") or story_path(latest["id"], latest["title"]),
            "published_at": latest.get("published_at"),
        },
    }
    path = data_dir / "notify.json"
    temporary = data_dir / "notify.json.tmp"
    _write_text(temporary, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


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
    images_source = READER_DIR / "images"
    if images_source.is_dir():
        images_dest = destination / "images"
        if images_dest.exists():
            shutil.rmtree(images_dest)
        shutil.copytree(images_source, images_dest)
    privacy_source = READER_DIR / "privacy" / "index.html"
    privacy_dest = destination / "privacy"
    privacy_dest.mkdir(exist_ok=True)
    privacy_html = privacy_source.read_text(encoding="utf-8").replace("/app/", "../")
    (privacy_dest / "index.html").write_text(privacy_html, encoding="utf-8")
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


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        target = str(path.resolve())
        if not target.startswith("\\\\?\\"):
            target = "\\\\?\\" + target
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return
    path.write_text(text, encoding="utf-8")


def _attach_blog_urls(stories: list[dict]) -> None:
    for story in stories:
        if not _is_original_story(story):
            continue
        href = f"{SITE}/{blog_path(story['id'], story['title'])}"
        story["blog_path"] = blog_path(story["id"], story["title"])
        for article in story.get("articles") or []:
            if is_original_source_name(article.get("source_name")):
                article["url"] = href


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
        _write_text(page, _story_page(story))
        _write_text(folder / "index.html", _story_redirect(story, slug))
    for child in list(root.iterdir()):
        if child.is_dir() and child.name not in keep:
            shutil.rmtree(child)


def _write_blog_pages(destination: Path, originals: list[dict]) -> None:
    root = destination / "blog"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    _write_text(root / "index.html", _blog_index_page(originals))
    for story in originals:
        slug = story_slug(story["title"])
        folder = root / str(story["id"]) / slug
        folder.mkdir(parents=True, exist_ok=True)
        _write_text(folder / "index.html", _blog_article_page(story, originals))
        _write_text(root / str(story["id"]) / "index.html", _blog_redirect(story, slug))


def _write_discovery(destination: Path, catalog: dict, originals: list[dict] | None = None) -> None:
    stories = catalog["stories"]
    originals = originals if originals is not None else [story for story in stories if _is_original_story(story)]
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
    _write_text(index, page.replace(HOME_MARKER, listing, 1))
    updated = (catalog.get("generated_at") or "")[:10]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        "  <url>",
        f"    <loc>{SITE}/</loc>",
        f"    <lastmod>{escape(updated)}</lastmod>" if updated else "",
        "  </url>",
        "  <url>",
        f"    <loc>{SITE}/blog/</loc>",
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
    for story in originals:
        published = str(story.get("published_at") or "")[:10]
        path = story.get("blog_path") or blog_path(story["id"], story["title"])
        lines.extend(
            [
                "  <url>",
                f"    <loc>{SITE}/{escape(path, quote=True)}</loc>",
                f"    <lastmod>{escape(published)}</lastmod>" if published else "",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    _write_text(destination / "sitemap.xml", "\n".join(line for line in lines if line) + "\n")
    _write_text(
        destination / "robots.txt",
        "User-agent: *\nAllow: /\n\nSitemap: https://edulens360.com/sitemap.xml\n",
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
    original = _is_original_story(story)
    sources = "Edulens360 tip" if original else ("1 source" if count == 1 else f"{count} sources")
    image = _http_url(story.get("image_url"))
    photo = ""
    if image:
        photo = (
            f'<img class="card-photo" alt="{title}" '
            f'src="{escape(image, quote=True)}" referrerpolicy="no-referrer">'
        )
    blocks = "\n".join(_source_block(article) for article in _public_articles(story))
    data = json.dumps(_saved_copy(story), ensure_ascii=False).replace("<", "\\u003c")
    image_meta = f'<meta property="og:image" content="{escape(image, quote=True)}">' if image else ""
    twitter_card = "summary_large_image" if image else "summary"
    robots = '<meta name="robots" content="index,follow,max-image-preview:large">'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#1c3d2e">
  <title>{title} · Edulens360</title>
  <meta name="description" content="{description}">
  {robots}
  <link rel="canonical" href="{canonical}">
  <meta property="og:site_name" content="Edulens360">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:locale" content="en_GH">
  {image_meta}
  <meta name="twitter:card" content="{twitter_card}">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  {f'<meta name="twitter:image" content="{escape(image, quote=True)}">' if image else ""}
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
    <div class="categories">
      <div class="cat-bar">
        <a href="../../../">Latest</a>
        <a href="../../../">Categories</a>
        <a href="../../../#/saved">Saved</a>
      </div>
    </div>
  </header>
  <main id="main">
    <article class="story">
      <a class="back" href="../../../" aria-label="Back to latest">Back</a>
      <p class="kicker">{label} · {when} · {sources}</p>
      <div class="headline"><h1>{title}</h1>{photo}</div>
      <p class="summary">{summary}</p>
      <div class="actions">
        <button type="button" class="secondary" id="share-story">Share</button>
        <button type="button" id="save-story">Save</button>
      </div>
      {blocks}
    </article>
  </main>
  <script type="application/json" id="story-data">{data}</script>
  <script>
    const story = JSON.parse(document.getElementById("story-data").textContent);
    const button = document.getElementById("save-story");
    const share = document.getElementById("share-story");
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
    share.addEventListener("click", async () => {{
      const url = story.path
        ? new URL(story.path, "https://edulens360.com/").href
        : location.href;
      const title = story.title || "Edulens360";
      const text = story.summary || story.title || "Edulens360";
      if (window.EdulensShare && typeof window.EdulensShare.share === "function") {{
        try {{
          window.EdulensShare.share(title, text, url);
          return;
        }} catch (error) {{}}
      }}
      if (navigator.share) {{
        try {{
          await navigator.share({{ title, text, url }});
          return;
        }} catch (error) {{
          if (error && error.name === "AbortError") return;
        }}
      }}
      try {{
        await navigator.clipboard.writeText(url);
        share.textContent = "Link copied";
      }} catch (error) {{}}
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
    name = article.get("source_name") or "Source"
    excerpt = article.get("excerpt") or ""
    if is_original_source_name(name):
        lead = tip_lead(excerpt) if excerpt else ""
        text = f'<p class="summary">{escape(lead)}</p>' if lead else ""
    else:
        text = f'<p class="summary">{escape(excerpt)}</p>' if excerpt else ""
    safe_name = escape(name)
    url = escape(article.get("url") or "", quote=True)
    return (
        '<section class="source">'
        f"<h3>{safe_name}</h3>"
        f"{text}"
        f'<a class="link-button secondary" href="{url}" target="_blank" rel="noreferrer">Read at {safe_name}</a>'
        "</section>"
    )


def _is_original_story(story: dict) -> bool:
    sources = story.get("sources") or []
    return len(sources) == 1 and is_original_source_name(sources[0])


def _original_excerpt(story: dict) -> str:
    for article in story.get("articles") or []:
        if is_original_source_name(article.get("source_name")):
            return article.get("excerpt") or ""
    return ""


def _blog_redirect(story: dict, slug: str) -> str:
    title = escape(story["title"])
    target = escape(slug + "/", quote=True)
    path = story.get("blog_path") or blog_path(story["id"], story["title"])
    canonical = escape(f"{SITE}/{path}", quote=True)
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


def _blog_index_page(originals: list[dict]) -> str:
    items = []
    for story in originals:
        path = story.get("blog_path") or blog_path(story["id"], story["title"])
        when = escape(_format_when(story.get("published_at")))
        items.append(
            "<li>"
            f'<a href="{escape(path.removeprefix("blog/"), quote=True)}">{escape(story["title"])}</a>'
            f'<span class="meta">{when}</span>'
            "</li>"
        )
    listing = "\n        ".join(items) if items else "<li>No tips published yet.</li>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#1c3d2e">
  <title>Edulens360 tips · Edulens360</title>
  <meta name="description" content="Practical education tips from Edulens360 for students, teachers, and parents in Ghana.">
  <meta name="robots" content="index,follow">
  <link rel="canonical" href="{SITE}/blog/">
  <meta property="og:site_name" content="Edulens360">
  <meta property="og:title" content="Edulens360 tips">
  <meta property="og:description" content="Practical education tips from Edulens360 for students, teachers, and parents in Ghana.">
  <meta property="og:url" content="{SITE}/blog/">
  <meta property="og:type" content="website">
  <link rel="icon" href="../icon-192.png">
  <link rel="stylesheet" href="../styles.css?v={SHELL_VERSION}">
</head>
<body>
  <header>
    <div class="bar">
      <a class="brand" href="../"><img src="../logo.svg" alt="Edulens360" width="64" height="56"></a>
    </div>
  </header>
  <main id="main">
    <article class="story">
      <a class="back" href="../" aria-label="Back to latest">Back</a>
      <p class="kicker">Edulens360 · Tips</p>
      <div class="headline"><h1>Edulens360 tips</h1></div>
      <p class="summary">Practical guidance for students, teachers, and parents in Ghana.</p>
      <ul class="blog-index">
        {listing}
      </ul>
    </article>
  </main>
</body>
</html>
"""


def _blog_article_page(story: dict, originals: list[dict]) -> str:
    title = escape(story["title"])
    summary = escape(story.get("summary") or "")
    path = story.get("blog_path") or blog_path(story["id"], story["title"])
    canonical = escape(f"{SITE}/{path}", quote=True)
    description = escape(_plain(story.get("summary") or "", 180), quote=True)
    label = escape(CATEGORY_LABELS.get(story.get("category") or "", "") or "Education")
    when = escape(_format_when(story.get("published_at")))
    image = _http_url(story.get("image_url"))
    photo = ""
    if image:
        photo = (
            f'<img class="card-photo" alt="{title}" '
            f'src="{escape(image, quote=True)}" referrerpolicy="no-referrer">'
        )
    body = format_tip_body_html(tip_body_without_related(_original_excerpt(story)))
    related = []
    for other in originals:
        if other["id"] == story["id"]:
            continue
        other_path = other.get("blog_path") or blog_path(other["id"], other["title"])
        href = escape("../../" + other_path.removeprefix("blog/"), quote=True)
        related.append(f'<li><a href="{href}">{escape(other["title"])}</a></li>')
    more = "\n          ".join(related[:8])
    more_block = (
        '<section class="blog-more">'
        "<h2>More from Edulens360</h2>"
        f"<ul>\n          {more}\n        </ul>"
        '<p class="blog-links">'
        '<a href="../../">All Edulens360 tips</a>'
        " · "
        '<a href="../../../">Latest education news</a>'
        "</p>"
        "</section>"
        if related
        else (
            '<section class="blog-more">'
            '<p class="blog-links">'
            '<a href="../../">All Edulens360 tips</a>'
            " · "
            '<a href="../../../">Latest education news</a>'
            "</p>"
            "</section>"
        )
    )
    image_meta = f'<meta property="og:image" content="{escape(image, quote=True)}">' if image else ""
    twitter_card = "summary_large_image" if image else "summary"
    schema = dict(_article_schema(story, image))
    schema["mainEntityOfPage"] = f"{SITE}/{path}"
    schema["author"] = {"@type": "Organization", "name": "Edulens360", "url": SITE + "/"}
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#1c3d2e">
  <title>{title} · Edulens360</title>
  <meta name="description" content="{description}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{canonical}">
  <meta property="og:site_name" content="Edulens360">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:locale" content="en_GH">
  {image_meta}
  <meta name="twitter:card" content="{twitter_card}">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  {f'<meta name="twitter:image" content="{escape(image, quote=True)}">' if image else ""}
  <link rel="icon" href="../../../icon-192.png">
  <link rel="stylesheet" href="../../../styles.css?v={SHELL_VERSION}">
  <script type="application/ld+json">
    {json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c")}
  </script>
</head>
<body>
  <header>
    <div class="bar">
      <a class="brand" href="../../../"><img src="../../../logo.svg" alt="Edulens360" width="64" height="56"></a>
    </div>
  </header>
  <main id="main">
    <article class="story">
      <a class="back" href="../../../" aria-label="Back to latest">Back</a>
      <p class="kicker">{label} · {when} · Edulens360 tip</p>
      <div class="headline"><h1>{title}</h1>{photo}</div>
      <p class="summary">{summary}</p>
      <section class="tip-body">
        {body}
      </section>
      {more_block}
    </article>
  </main>
</body>
</html>
"""


def _article_schema(story: dict, image: str) -> dict:
    published = _iso_date(story.get("published_at"))
    original = _is_original_story(story)
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": story["title"],
        "description": _plain(story.get("summary") or "", 180),
        "datePublished": published,
        "dateModified": published,
        "mainEntityOfPage": f"{SITE}/{story['path']}",
        "author": {
            "@type": "Organization",
            "name": "Edulens360" if original else (story.get("sources") or ["Edulens360"])[0],
            "url": SITE + "/",
        },
        "publisher": {
            "@type": "Organization",
            "name": "Edulens360",
            "url": SITE + "/",
            "logo": {
                "@type": "ImageObject",
                "url": f"{SITE}/icon-512.png",
            },
        },
        "isAccessibleForFree": True,
    }
    if image:
        schema["image"] = [image]
    return schema


def _iso_date(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value.strip()
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
