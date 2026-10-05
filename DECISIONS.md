# Decisions

## ADR-001 — SQLite for the local database

Date: 2026-10-05

Context: The MVP has to run at no cost and without linking a card. PostgreSQL is the preferred long-term database, and installing it is extra local setup before any product feature exists.

Decision: Use SQLite through SQLAlchemy for the MVP. Keep the database URL in the environment so a PostgreSQL URL can replace it later. Record the hosting change as PROD-001.

Alternatives considered: Local PostgreSQL now. A hosted free database. An in-memory database only.

Reason: SQLite is a single file, needs no account, and is enough for one developer and one collector process. SQLAlchemy and Alembic avoid painting the schema into SQLite-only application code. `render_as_batch` is enabled so later column changes still have a path to PostgreSQL.

Consequences: Only one writer should use the file. Tests create their own temporary database files. The file is gitignored.

Production implications: Replace the file with managed PostgreSQL before public launch. See PROD-001.

## ADR-002 — One Python process

Date: 2026-10-05

Context: Ingestion will need a schedule. A separate queue such as Redis or Celery adds services to install and run before there is any data.

Decision: Keep the API in one FastAPI process. A later phase can run the scheduler inside that process. Do not add Redis, Celery, Kafka, or a second deployable service in the foundation.

Alternatives considered: Celery with Redis. A second worker process from the start.

Reason: One process is free, understandable, and enough for a small set of RSS feeds. The ingestion code can move behind a queue later without changing the database model.

Consequences: A long fetch can share the API process. That is acceptable while the only user is the developer. Fetching is not part of Phase 1.

Production implications: Move scheduled work to a queue when one process can no longer finish fetches on time or when the API and the collector need to restart independently. That item will be added to the debt register in the phase that introduces the scheduler.

## ADR-003 — Python 3.12

Date: 2026-10-05

Context: This PC has Python 3.12 and Python 3.14. Library wheels and FastAPI tooling are predictable on 3.12.

Decision: Develop and test on Python 3.12. The virtual environment is created with `py -3.12`.

Alternatives considered: Python 3.14 as the default interpreter.

Reason: 3.12 is the stable choice for the current FastAPI and SQLAlchemy releases. 3.14 can stay installed for other work.

Consequences: Commands in the README use `py -3.12`. The backend records `.python-version` as `3.12`.

Production implications: The future host should run Python 3.12 unless a later decision upgrades it.

## ADR-004 — Domain tables start in the phase that uses them

Date: 2026-10-05

Context: The full product needs sources, articles, stories, categories, and users. Creating those tables before their behavior exists would freeze an unused schema.

Decision: Phase 1 ships a baseline Alembic revision with no domain tables. The source model arrives with Phase 2, in a new revision.

Alternatives considered: Generate the whole data model up front.

Reason: Empty tables do not prove the product, and early columns tend to be rewritten once ingestion is real.

Consequences: `/health` only runs `SELECT 1`. It does not require a news table. `app/db/models` is reserved for the next phase.

Production implications: None beyond the normal rule that every schema change ships as a migration.

## ADR-005 — Publishers live in the database

Date: 2026-10-05

Context: The pipeline has to read several Ghanaian publishers, and those publishers will change. Hard-coding site addresses into fetch code would require an application change every time a feed moves or a source should be paused.

Decision: Store each publisher in the `sources` table. Add, edit, disable, and remove them through `/sources`. Keep a checked starter list in `app/sources/catalog.py` and load it with `python -m app.db.seed`. The seed inserts missing names and does not overwrite later edits. Store a feed URL only after that address has returned RSS.

Alternatives considered: A JSON file as the only registry. Hard-coded Python constants inside the future fetcher. Scraping any site that mentions Ghana education.

Reason: The acceptance test for this phase is that a source can be disabled without changing application code. A database row does that. The catalog is only the initial data, and the notes record what was actually checked on 2026-10-05.

Consequences: Phase 3 must select active rows from `sources` instead of its own list. Sources with an empty `feed_url` stay in the registry and are not fetched until a feed exists. Trust scores in the catalog are starting defaults.

Production implications: Adding a publisher stays a data change. Revisit a feed address when ingestion starts failing for that source. No new hosted service is required.

## ADR-006 — Store feed excerpts, and schedule fetches in this process

Date: 2026-10-05

Context: RSS feeds often embed the full article HTML. The product is an aggregator, so the database should keep enough text to show a headline and a short excerpt, plus the link back to the publisher. Fetching has to run on a schedule without adding Redis or another service.

Decision: Persist the feed title, link, date, author, image URL, and a plain-text excerpt capped at 1,000 characters. Do not store `content:encoded` or the rest of the article body. Fetch active RSS sources from a background thread in the API process, every five minutes, and only when each source's own crawl interval has elapsed. A manual run is `POST /ingestion/run` or `python -m app.ingestion`. Ask feeds for uncompressed bytes because one publisher's compressed response could not be decoded. Cap a robots `Crawl-delay` at 30 seconds. If `robots.txt` is missing or unreachable, fetch the public feed; if it disallows the feed, skip that source and record the failure.

Alternatives considered: Saving the raw feed XML. Downloading each article page. APScheduler plus Redis. Refusing to fetch whenever `robots.txt` cannot be downloaded.

Reason: A capped excerpt is enough for this phase and keeps the app from becoming a republisher. One thread matches ADR-002. Uncompressed responses made Adom Online readable. An explicit robots disallow is respected; a missing robots file should not block a public feed.

Consequences: Phase 4 relevance runs on the excerpt and title, not on the full article. A source with an empty feed succeeds and stores nothing. Disabled sources and sources without a feed URL are skipped. Deleting a source that already has articles returns 409.

Production implications: The schedule still runs only while this PC runs the API. See PROD-002. Full-text extraction, if it is ever added, needs its own legal review before anything longer than an excerpt is kept.

## ADR-007 — Keyword relevance, with a Ghana-source prior

Date: 2026-10-05

Context: The feed has to drop sports, politics, and foreign education news before a person reads it. The stored text is a title and a short excerpt. A paid model is out of scope. Many real Ghana education stories, including teacher strikes, never put the word Ghana in the headline because the publisher is already Ghanaian.

Decision: Score Ghana and education separately with editable keyword lists. Publish only when both scores reach `RELEVANCE_PUBLISH_THRESHOLD` (default 0.6). Reject when either score is below `RELEVANCE_REJECT_THRESHOLD` (default 0.35). Hold the rest for review. Store both scores, the decision, and the matched terms. If `sources.covers_ghana` is true, raise the Ghana score to at least 0.66 and say so in the reason. Leave the education score unchanged. New articles are scored during ingestion. `POST /relevance/run?force=true` rescores after a rule edit.

Alternatives considered: One combined keyword list. A hosted classifier. Treating every story from a Ghanaian site as relevant. Fetching the full article before scoring.

Reason: Separate scores keep a Ghana football story and a Harvard admissions story out for different, testable reasons. The source prior fixes the teacher-strike miss without publishing sports. Thresholds stay in configuration so they can move without a code edit to the term lists.

Consequences: A single education word in the excerpt of a Ghanaian story stays in review. School infrastructure needs a strong education term, or a strong term plus a weak one such as "school", before it publishes. The rules will miss some stories and pass some borderline ones. That is the signal for PROD-004, not a reason to add a model now.

Production implications: Keyword lists are an MVP shortcut. Replace them with a local model only after personal use shows the same kinds of misses repeating. See PROD-004. No external scoring service is required.

## ADR-008 — Group the same event with titles, and summarize from the excerpt

Date: 2026-10-05

Context: Several publishers cover one event, especially the teacher strike, with different headlines. The reader should see one story, not thirty copies. The only text available is the title and the capped excerpt. A paid embedding service is out of scope.

Decision: Group only articles whose relevance decision is `publish`. Join two articles when their important title words overlap by at least 0.55 within seven days, or when both headlines are about a teacher strike within fourteen days. Give the story a category from a keyword list, a title chosen from the member headlines, and a summary of at most two sentences from the highest-trust excerpt, capped at 320 characters. New articles are grouped at the end of ingestion. `POST /stories/build?force=true` rebuilds every group.

Alternatives considered: One story per article. Embedding similarity. A hosted clustering API. Rewriting the excerpt into a new summary.

Reason: Title overlap catches near-duplicate headlines. The strike rule catches the same event when the wording changes. The summary stays inside text the publisher already supplied, so the app does not become a rewriter or a republisher.

Consequences: Related articles that use different words, such as promotion-arrears stories that never say "strike", stay separate. A fourteen-day gap can split a long-running event. That is the signal for PROD-005.

Production implications: This grouping is an MVP shortcut. Replace it with local similarity only if personal use shows the same bad groups repeating. See PROD-005. No external clustering service is required.

## ADR-009 — Rank the reader feed in this process

Date: 2026-10-05

Context: A reader should see the teacher strike, covered by three publishers, ahead of a one-off college notice from the same hour. The phone is not built yet. Search has to work without a paid search service, and the response must stay a summary plus a link.

Decision: `GET /feed` ranks stored stories when it is called. The score is 0.55 recency of the newest article in the story, with a 36-hour half-life, 0.30 coverage from the count of distinct publishers up to three, and 0.15 from the average relevance score. The weights live in configuration and must add up to 1. Time is taken at the current hour so the list and a story page agree. `GET /feed/search` matches whole words in the story title, the summary, and member headlines. `GET /feed/{id}` returns publisher names, original links, and excerpts. It does not return an article body. `/stories` stays the engine route that rebuilds groups.

Alternatives considered: Chronological order only. A hosted search index. Ranking by article count, which would reward one site posting the same story many times. Searching the full excerpt.

Reason: Coverage by distinct publishers surfaces the event people are repeating, without letting one feed flood the list. Word search on headlines and the summary answers the phase without scanning article text the product is not allowed to republish. Computing the rank on read means it ages without a rebuild.

Consequences: A story the ranker undervalues stays lower until the weights change. Search misses a story whose headline and summary never use the query word. A few hundred stories are cheap to score in this process. A much larger file is the signal for PROD-006.

Production implications: In-process rank and search are an MVP shortcut. Add a local index only if the feed gets slow or the order is systematically wrong. See PROD-006. No external search service is required.

## ADR-010 — A local review desk, with no accounts

Date: 2026-10-05

Context: Some articles are held because the keyword score is unsure, and a generated story title is not always the one a person wants on the feed. The desk is for the person running this PC. Accounts, passwords, and a public login are deferred.

Decision: Serve `GET /review` from this process. Approving a held article marks it publish and groups it. Rejecting it marks it reject and removes it from its story. Hiding a story sets `reader_visible` false so `GET /feed` and `GET /feed/{id}` omit it. A saved title or summary is stored next to the generated text and is what the reader sees. A normal fetch refreshes the generated text and leaves the saved text. `POST /stories/build?force=true` deletes stories, so it clears saved edits. Disabling a source stays `PATCH /sources/{id}` with `{"active": false}`.

Alternatives considered: A separate admin site. User accounts. Letting a fetch overwrite a saved title. Putting the desk on the phone.

Reason: One page on this PC is enough to correct the feed before anyone reads it. Keeping the saved text beside the generated text means a new article can still join the story without erasing the edit.

Consequences: Anyone who can open this API can approve, hide, or edit. That is acceptable only while the API stays on this PC. See PROD-007.

Production implications: Add a local password before this API is reachable beyond this PC. No hosted login service is required for the personal MVP.

## ADR-011 — An installable page, with saves kept on the device

Date: 2026-10-05

Context: The reader feed is JSON. A phone needs a page for the latest stories, categories, one story, and the link back to the publisher. Accounts and a store app are out of scope. The page has to be installable without a paid service.

Decision: Serve a static page at `GET /app/` from this process. It calls the reader feed on the same origin. A web app manifest and a service worker make it installable. The service worker caches the page shell. Saves are stored in the browser's local storage, including the summary and the publisher links, so a saved story can be opened on that device when the feed is down. There is no account and no sync.

Alternatives considered: A Flutter app. A hosted login for saves. Caching the whole feed in the service worker now. Binding the API to the local network so a phone can reach this PC.

Reason: One page can be installed from the browser and later copied to GitHub Pages. Local storage matches the promise that saves stay on the device. Opening the API to the whole network would also expose the review desk, which has no login.

Consequences: A phone that is not this PC cannot open `127.0.0.1`. That publish step is Phase 9. Saves disappear if the browser storage for this site is cleared. They do not follow the person to another device.

Production implications: The page still depends on this PC for a live feed. See PROD-002. Phase 9 publishes a copy. No store account and no paid host are required.

## ADR-012 — Publish a static copy, and keep the previous one when an export is empty

Date: 2026-10-05

Context: A phone that is not this PC cannot open `127.0.0.1`. The reader has to be a set of files a free static host can serve. The review desk must stay on this PC. A bad fetch must not wipe the copy the phone already has.

Decision: `python -m app.publish` writes the reader into `docs/` and one `data/feed.json` built from visible stories. The file holds the summary, the publisher, the original link, and the excerpt. It does not hold a full article. The published page reads that file. Its service worker stores the last feed that loaded. If the export has no stories and `docs/data/feed.json` already has some, the command refuses and leaves the file. `scripts/refresh.ps1` fetches, then publishes, then pushes `docs/` only when a GitHub `origin` exists and the copy changed. The Windows task runs that script every 30 minutes.

Alternatives considered: Opening the API to the local network. Publishing the review desk. Replacing a good feed with an empty file so the phone matches a failed database.

Reason: GitHub Pages can serve `docs/` at no cost. Keeping the API on this PC leaves the review desk unexposed. Refusing an empty export is the last good copy on disk. The service worker is the last good copy on the phone.

Consequences: The phone sees a snapshot, not a live API. New stories appear after the next successful publish. Saves still stay on the device. There is no GitHub remote on this PC yet, so the task writes `docs/` and does not push.

Production implications: The collector still stops when this PC is off. The phone keeps the last pushed copy. See PROD-002.


