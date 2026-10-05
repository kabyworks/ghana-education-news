# Architecture

Ghana Education News is a local engine that publishes a phone-readable copy. Phase 9 writes that copy into `docs/` and refreshes it on a Windows schedule.

## What runs today

```text
Background thread, every 5 minutes
        |
        v
Active RSS sources whose crawl interval has elapsed
        |
        v
Feed fetch -> excerpt -> relevance score -> story group -> articles and stories tables
        |
        +--> source health (last success or last error)

Browser or test client
        |
        v
FastAPI process
        |
        v
SQLite file  (backend/data/ghanaed.db)
```

`POST /ingestion/run` forces a pass immediately. Sources with no feed URL, and inactive sources, are skipped.

## Layout

```text
backend/
    app/
        main.py                 creates the FastAPI app and starts the scheduler
        api/routes/             health, sources, articles, ingestion, relevance, stories, feed, review
        review/desk.html        local review page
        reader/                 installable phone page
        publish/                static phone copy written to docs/
        core/                   settings and logging
        db/                     engine, sessions, migrations, seed command
        db/models/              Source, Article, Story
        ingestion/              RSS parser, fetch client, pipeline, scheduler
        intelligence/relevance/ keyword scorer and rescore command
        intelligence/stories/   event grouping, categories, extractive summary
        intelligence/feed/      reader rank
        services/               source, article, story, feed, and review operations
        sources/catalog.py      starter publishers checked on 2026-10-05
    migrations/
    tests/
    data/                       local SQLite file, not committed
```

`docs/` is the phone site. `scripts/refresh.ps1` fetches and rewrites it. The next reliability pass hardens backups and failure handling.

## Request path

`create_app()` loads settings, configures logging, and registers the routes. When `INGESTION_ENABLED` is true, a daemon thread calls the pipeline on startup and then every `INGESTION_INTERVAL_SECONDS`. Each pass opens its own database session. `/health` still only runs `SELECT 1`.

A fetch reads `robots.txt` first. An explicit disallow is recorded as a source failure. The feed body is parsed as RSS. Each new canonical URL is scored before it is stored. The excerpt is plain text capped at 1,000 characters. The original URL is kept for attribution.

Scoring is two keyword scores, Ghana and education. Either score below the reject threshold rejects the article. Both scores at or above the publish threshold publish it. Everything else is held for review. Terms live in `app/intelligence/relevance/terms.py`. A source with `covers_ghana` true has its Ghana score raised to at least 0.66, so a Ghanaian outlet's education story can publish even when the headline never says Ghana. That floor does not invent an education score. `GET /articles?decision=publish` returns one decision. `POST /relevance/run?force=true` scores stored articles again after a rule change.

Published articles are then grouped. Two headlines join the same story when their important words overlap within seven days, or when both are about the teacher strike within fourteen days. A new article joins an existing story during the next ingestion pass. The story title is chosen from the member headlines. The summary is the first two sentences of the highest-trust excerpt, capped at 320 characters. The category is a keyword label such as `teachers` or `higher_education`. `POST /stories/build?force=true` rebuilds the groups after a rule change. Rejected articles are left out.

`GET /feed` is what a reader calls. Each story gets a rank from three parts: recency of its newest article, with a 36-hour half-life, the number of distinct publishers up to three, and the average relevance score. Weights are `FEED_RANK_RECENCY_WEIGHT` (0.55), `FEED_RANK_COVERAGE_WEIGHT` (0.30), and `FEED_RANK_RELEVANCE_WEIGHT` (0.15). The clock is the current hour, so the list and a story page opened together show the same rank. `GET /feed/categories` returns categories that contain stories. `GET /feed/search?q=` matches a story title, its summary, and the headlines inside it. `GET /feed/{id}` adds the publisher, the original link, and the stored excerpt. It does not add the article body. `/stories` stays the engine view used to rebuild groups.

`GET /review` is a page for this PC. It lists articles whose relevance decision is `review`, every story, and every source. Approving an article marks it publish and groups it. Rejecting it keeps it out of stories. Hiding a story sets `reader_visible` false, and the reader feed then omits it. A saved title or summary is stored beside the generated text. The feed shows the saved text. The next fetch still refreshes the generated text and leaves the saved text in place. `POST /stories/build?force=true` deletes stories and clears those edits. Disabling a source is the existing `PATCH /sources/{id}` with `{"active": false}`.

`GET /app/` is the phone page on this PC. It is a static page with a web app manifest and a service worker, so a browser can install it. The page calls `GET /feed`, `GET /feed/categories`, and `GET /feed/{id}`. A story shows the summary, each publisher, and a link to the original. The response still has no article body. Saves are written to the browser's local storage on that device. The service worker caches the page shell. It does not publish the feed.

`python -m app.publish` copies that page into `docs/` and writes `docs/data/feed.json` from the visible stories. The published page reads that file instead of the API. Search and categories run in the browser over the file. The published service worker keeps the last feed it successfully loaded. If a later export contains no stories, the command stops and leaves the previous `feed.json` on disk. The review desk is not copied. GitHub Pages serves `docs/` once that folder is pushed and Pages is set to the `/docs` folder. Until then, a phone away from this PC cannot open the copy.

## Data

`sources` holds publishers, including `covers_ghana`. `articles` holds discovered items, the two dimension scores, the decision, the reason, and an optional `story_id`. `stories` holds the grouped title, summary, category, article count, and any review edit. Deleting a source that still has articles is rejected. Alembic revision `0007_review` is the current head.

The application does not migrate itself on startup. Apply migrations with `alembic upgrade head`.

## What the phone uses

On this PC the page is `http://127.0.0.1:8000/app/` while the API is running. The phone copy is the `docs/` folder. A phone away from this PC opens it only after GitHub Pages is turned on for that folder. The scheduled task `Ghana Education News refresh` runs `scripts/refresh.ps1` every 30 minutes and, once an `origin` remote exists, pushes a changed copy.

## Boundaries

- Source routes do not fetch articles. `POST /ingestion/run` is the manual trigger.
- AI calls, when they exist, stay behind a replaceable provider. There is no AI in this phase.
- Stored text is an excerpt. Full article HTML from a feed is not kept.
