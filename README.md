# Ghana Education News

Ghana Education News collects public education news into one feed. This repository is the local engine for that product. Phase 9 writes an installable phone copy into `docs/`. Each item is a summary plus links back to the publishers. A phone away from this PC can open that copy after it is on GitHub Pages.

## What works now

- `GET /` identifies the service.
- `GET /health` checks that the API and the database are up.
- `GET /docs` shows the interactive API page.
- Sources can be added, listed, updated, disabled, and removed through `/sources`.
- Active RSS sources are fetched on a schedule. Repeated links are skipped. One failed source does not stop the others.
- `GET /articles` lists what has been stored. Add `?decision=publish`, `reject`, or `review` to filter.
- New articles are scored as they are stored. `POST /relevance/run` scores older rows that have no decision. Add `?force=true` to score every stored article again.
- Published articles are grouped into stories. `GET /stories` is the engine list. `POST /stories/build?force=true` rebuilds the groups.
- `GET /feed` is the reader list, ranked by recency, how many publishers covered the story, and relevance.
- `GET /feed/categories` lists categories. `GET /feed/search?q=strike` searches headlines and summaries.
- `GET /feed/{id}` opens one story with the publisher, the original link, and the excerpt.
- `GET /review` is the local review desk: approve or reject a held article, hide or edit a story, and disable a source.
- `GET /app/` is the installable phone page on this PC: latest stories, categories, one story, the publisher link, and saves kept in the browser on that device.
- `python -m app.publish` writes the same page into `docs/` with the current feed baked in. An empty export leaves the previous `docs/data/feed.json` in place.
- `scripts/refresh.ps1` fetches, then publishes. The scheduled task `Ghana Education News refresh` runs that every 30 minutes. When a GitHub `origin` exists, a changed copy is committed and pushed.
- A database failure returns a generic error and keeps the details in the log.

## Setup

Use Python 3.12. From PowerShell:

```powershell
cd "C:\Users\Kaby\mycursorcode\GhanaEd News\backend"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.db.seed
.\.venv\Scripts\python.exe -m app.ingestion
```

`.env` stays on your machine. `.env.example` is the safe template.

## Run

```powershell
cd "C:\Users\Kaby\mycursorcode\GhanaEd News\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000/app/](http://127.0.0.1:8000/app/) for the phone page and [http://127.0.0.1:8000/review](http://127.0.0.1:8000/review) for the review desk.

To fetch again without waiting for the schedule:

```powershell
.\.venv\Scripts\python.exe -m app.ingestion
```

Or send `POST /ingestion/run` from the docs page.

To score articles that do not have a decision yet:

```powershell
.\.venv\Scripts\python.exe -m app.intelligence.relevance
```

To rebuild story groups after a rule change:

```powershell
.\.venv\Scripts\python.exe -m app.intelligence.stories --force
```

To refresh the phone copy in `docs/`:

```powershell
.\.venv\Scripts\python.exe -m app.publish
```

To register the 30-minute task again:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "..\scripts\register-refresh.ps1"
```

## Test

```powershell
cd "C:\Users\Kaby\mycursorcode\GhanaEd News\backend"
.\.venv\Scripts\python.exe -m pytest
```

## Project record

- [PROJECT_STATE.md](PROJECT_STATE.md) — where the build is
- [ARCHITECTURE.md](ARCHITECTURE.md) — how the pieces fit
- [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) — shortcuts to replace before real scale
- [DECISIONS.md](DECISIONS.md) — why the foundation is built this way
- [SOURCES.md](SOURCES.md) — the checked starter publishers
- [TODO.md](TODO.md) — what comes next
