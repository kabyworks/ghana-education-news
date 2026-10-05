# Project State

## Current Phase

Phase 9 — Publishing. The phone copy is built on this PC. A public GitHub Pages address is still waiting on a GitHub login.

## Completed

- FastAPI application with `GET /`, `GET /health`, and `GET /docs`.
- Environment configuration through `.env` and process variables.
- SQLite database path resolution and SQLAlchemy session setup.
- Alembic migrations through `0007_review`.
- Console logging.
- Source registry: create, list, update, disable, and delete publishers through `/sources`.
- Source health fields, written only by `record_source_check`, not by API clients.
- Starter catalog of sources checked on 2026-10-05, loaded with `python -m app.db.seed`.
- RSS ingestion for active sources that have a feed URL.
- Duplicate links are skipped. One failed source does not stop the others.
- A background pass every five minutes while the API process is running.
- Automated tests for configuration, health, migrations, sources, and ingestion.
- Each new article is scored for Ghana and for education from its title and excerpt.
- Decisions are `publish`, `reject`, or `review`, with the matched terms stored on the article.
- Thresholds are `RELEVANCE_PUBLISH_THRESHOLD` (0.6) and `RELEVANCE_REJECT_THRESHOLD` (0.35).
- A source marked `covers_ghana` gets a Ghana-score floor so education stories that never say "Ghana" can still publish. Sports and politics with no education terms still reject.
- `GET /articles?decision=publish` filters the stored decision. `POST /relevance/run` scores articles that have no decision yet. `force=true` scores them again.
- Published articles are grouped into stories. The same teacher-strike event becomes one story. Separate events stay separate.
- Each story has a category, an article count, and an extractive summary taken from a stored excerpt.
- `GET /stories` lists stories. `GET /stories/{id}` lists the member headlines, sources, and excerpts. Rejected articles are not grouped.
- `POST /stories/build` groups articles that are not in a story yet. `force=true` rebuilds every story.
- `GET /feed` is the reader list. It ranks stories by the newest article, how many publishers covered them, and their relevance score.
- `GET /feed/categories` lists categories that have stories. `GET /feed?category=teachers` filters the list.
- `GET /feed/search?q=strike` matches story headlines, summaries, and the headlines inside a story.
- `GET /feed/{id}` opens one story with publisher names, links, and excerpts. The response has no full article text.
- `GET /review` is the local review desk. Held articles can be approved or rejected. Approving one lets it become a story.
- A story can be hidden, which removes it from `GET /feed`, or shown again. A saved title or summary is what the reader sees, and a normal fetch does not wipe it.
- A source can be turned off from the desk with the same `PATCH /sources/{id}` action as the API. `{"active": false}` stops fetching.
- `GET /app/` is the installable phone page. It lists the reader feed, filters by category, opens one story, and links to the publisher.
- Saves stay in the browser on that device. They are not accounts and they do not sync.
- `python -m app.publish` writes a static phone site to `docs/`. It includes the reader page and `data/feed.json`. The review desk is not in that folder.
- An empty export does not replace a copy that already has stories.
- The published page caches the last feed it loaded, so the phone can still open that copy when the network is down.
- A Windows scheduled task, `Ghana Education News refresh`, fetches and republishes every 30 minutes while this user is logged on.
- This PC has no GitHub remote yet, so the task cannot push the copy. The phone still cannot open it away from this computer.

## In Progress

Putting `docs/` on GitHub Pages. The site files are ready. GitHub CLI was not installed, and this folder has no commits and no `origin` remote.

## Next Task

Sign in to GitHub, push `docs/`, and turn on Pages for the `/docs` folder. Then Phase 10 — reliability pass.

## Known Bugs

None.

## Production Debt Added

- PROD-001 — SQLite file on this PC.
- PROD-002 — The API process runs only while this PC is running it.
- PROD-003 — Logs go to the console.
- PROD-004 — Keyword relevance rules, to be replaced by a local model only if personal use shows systematic misses.
- PROD-005 — Title-and-keyword story grouping, to be replaced by local similarity only if personal use shows systematic bad groups.
- PROD-006 — In-process feed rank and search, to be replaced by a local index only if the feed gets slow or the order is systematically wrong.
- PROD-007 — The review desk has no login. Add a local password before this API is reachable beyond this PC.

Phase 9 writes a static copy and refuses to replace it with an empty feed. The copy still reaches a phone only after it is pushed to GitHub Pages. The collector still runs on this PC. See PROD-002.

## Tests

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.ingestion
.\.venv\Scripts\python.exe -m app.intelligence.relevance
.\.venv\Scripts\python.exe -m app.intelligence.stories --force
.\.venv\Scripts\python.exe -m app.publish
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/app/`.

## Current Architecture

One Python process serves the API, runs the ingestion thread, scores each new article, groups published articles into stories, and ranks the reader feed. It connects to a SQLite file at `backend/data/ghanaed.db`. Sources live in `sources`. Discovered articles live in `articles`. Stories live in `stories`. Schema changes go through Alembic.

## Important Decisions

- ADR-001 — SQLite for the local MVP database.
- ADR-002 — One Python process, with no separate worker queue yet.
- ADR-003 — Python 3.12.
- ADR-004 — Domain tables wait until the phase that needs them.
- ADR-005 — Publishers are database records, changed through the API.
- ADR-006 — Store feed excerpts, and schedule fetches in this process.
- ADR-007 — Keyword relevance, with a Ghana-source prior.
- ADR-008 — Group the same event with titles, and summarize from the excerpt.
- ADR-009 — Rank the reader feed in this process.
- ADR-010 — A local review desk, with no accounts.
- ADR-011 — An installable page, with saves kept on the device.
- ADR-012 — Publish a static copy, and keep the previous one when an export is empty.

## Do Not Break

- `/health` returns `503` with `Database unavailable` when the database check fails, and the response body does not include the underlying error.
- Secrets and the real `.env` file stay out of git.
- Schema changes go through a new Alembic revision.
- Run commands from the `backend` directory so imports and the database path resolve.
- Disabling a source is `PATCH /sources/{id}` with `{"active": false}`. The fetcher reads that flag from the database.
- Clients cannot set `last_checked_at`, `last_success_at`, or `last_error`.
- Do not store a feed URL that has not returned RSS.
- Do not store full article bodies. Excerpts stay capped at 1,000 characters.
- A source that still has articles cannot be deleted.
- Relevance reads the title and the capped excerpt. It does not fetch the article page.
- `covers_ghana` defaults to true. Set it false for a source that is not about Ghana.
- Story summaries are copied from a stored excerpt. They are not a rewrite and they are not the full article.
- Rejected articles stay out of stories.
- The reader feed is `GET /feed`. It does not include full article text. `/stories` remains the engine view.
- Hidden stories stay out of `GET /feed`. A saved title or summary is not replaced by the next fetch.
- Rebuilding every story with `POST /stories/build?force=true` clears those saved edits.
