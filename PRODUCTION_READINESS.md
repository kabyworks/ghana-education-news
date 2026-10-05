# Production Readiness

Shortcuts taken so the MVP can be built at no cost. Each one is acceptable for local development and has to change before the product serves the public at scale.

## PROD-001 — Database hosting

### Current MVP implementation

The API stores data in a SQLite file at `backend/data/ghanaed.db` on the development PC.

### Why it is acceptable for MVP

SQLite needs no separate database install, no account, and no card. SQLAlchemy keeps the application code on a normal database interface, and Alembic owns schema changes.

### Production problem

One file on one PC cannot serve real users, survive a disk failure, or accept concurrent writers from a hosted app and a worker.

### Production solution

Managed PostgreSQL with automated backups, restricted network access, and a migration rehearsal against a copy of real data.

### Trigger

Before a public launch, or as soon as the API must stay available while this PC is off.

### Priority

CRITICAL

### Status

NOT STARTED

## PROD-002 — Application hosting

### Current MVP implementation

The collector runs only when this PC runs it. Phase 9 writes a static phone copy to `docs/`. That copy is not on GitHub Pages until this folder has a remote and the copy is pushed.

### Why it is acceptable for MVP

Local hosting costs nothing and is enough to prove the engine. The phone feed will later be a static site, which still depends on this PC to collect new stories.

### Production problem

Stories stop updating when the PC is off, and there is no uptime monitoring, restart policy, or HTTPS API for a public client.

### Production solution

An always-on host for the collector and API, with a process manager that restarts on failure. The phone can keep reading a published feed during the move.

### Trigger

The feed must keep updating without this PC turned on.

### Priority

CRITICAL

### Status

NOT STARTED

## PROD-003 — Observability

### Current MVP implementation

Logs are written to the console of the process that starts the API.

### Why it is acceptable for MVP

Console logs are enough to see startup, shutdown, and a failed database check while developing.

### Production problem

Console output disappears when the terminal closes. There is no metric history, no alert when a source dies, and no shared place to inspect errors.

### Production solution

Centralized logs, basic metrics for fetch and publish runs, error tracking, and an alert when ingestion stops succeeding.

### Trigger

The first hosted deployment, before real readers depend on the feed.

### Priority

HIGH

### Status

NOT STARTED

## PROD-004 — Relevance model

### Current MVP implementation

Articles are scored with keyword lists for Ghana and for education. Thresholds live in configuration. A Ghanaian source gets a Ghana-score floor. The education score still has to come from the title or excerpt.

### Why it is acceptable for MVP

The rules are editable, testable, and free. On the 160 articles stored on 2026-10-05 they published teacher and college stories, rejected sports and politics with no education terms, and left three incidental mentions in review.

### Production problem

Keywords miss paraphrases and can treat one passing word as worth a review. A growing feed will keep producing the same kinds of mistakes.

### Production solution

Keep the keyword scorer as the fallback. Add a local model only after personal use shows the same misses repeating. Do not add a paid scoring API.

### Trigger

Systematic false rejects or false publishes during personal use.

### Priority

MEDIUM

### Status

NOT STARTED

## PROD-005 — Story grouping

### Current MVP implementation

Published articles join a story when their titles are similar within seven days, or when both headlines are about the teacher strike within fourteen days. The summary is copied from a stored excerpt.

### Why it is acceptable for MVP

On the 70 published articles stored on 2026-10-05, the strike coverage became one story of 29 articles. College announcements, school buildings, and the BECE starter-pack story stayed separate. Rejected sports and politics were not grouped.

### Production problem

Different wording for the same event can stay split, and a long-running event can break into a new story after fourteen days.

### Production solution

Keep this grouper as the fallback. Add local similarity only after personal use shows the same bad groups repeating. Do not add a paid clustering API.

### Trigger

Systematic missed groups or merged unrelated events during personal use.

### Priority

MEDIUM

### Status

NOT STARTED

## PROD-006 — Feed ranking and search

### Current MVP implementation

`GET /feed` scores every stored story in this process. Search scans story titles, summaries, and member headlines in Python.

### Why it is acceptable for MVP

Forty-two stories load and sort immediately. The rank uses recency, distinct publishers, and the relevance score already stored. No extra database or search host is required.

### Production problem

Scoring every story on each request, and scanning headlines in Python, will get slow once the file holds a long archive. The hand-tuned weights can also keep putting the wrong story first.

### Production solution

Keep this ranker as the fallback. Add a local index, still on this machine or the future host, only if the feed gets slow or personal use shows the same ordering mistakes. Do not add a paid search API.

### Trigger

The feed becomes slow, or the order is systematically wrong during personal use.

### Priority

MEDIUM

### Status

NOT STARTED

## PROD-007 — Review desk access

### Current MVP implementation

`GET /review` and the review actions have no login. The same is true of the rest of the API. The process listens on this PC only.

### Why it is acceptable for MVP

The desk is for the person at this computer. Nothing is exposed as a public site in this phase.

### Production problem

If the API is reachable from another machine, anyone can hide stories, change summaries, approve articles, or disable a source.

### Production solution

Add a local password, or another check that only this PC's operator can pass, before the API listens beyond localhost. Do not add a hosted account system for the personal MVP.

### Trigger

Before this API is reachable beyond this PC.

### Priority

HIGH

### Status

NOT STARTED

## Debt register

| ID | MVP shortcut | Production change | Trigger | Priority | Status |
| --- | --- | --- | --- | --- | --- |
| PROD-001 | SQLite file on this PC | Managed PostgreSQL with backups | Public launch or always-on hosting | Critical | Not started |
| PROD-002 | API runs only on this PC | Always-on application host | Feed must update while the PC is off | Critical | Not started |
| PROD-003 | Console logging | Centralized logs, metrics, and alerts | First hosted deployment | High | Not started |
| PROD-004 | Keyword relevance rules | A local model, if personal use shows the same misses repeating | Systematic false rejects or false publishes during personal use | Medium | Not started |
| PROD-005 | Title and keyword story grouping | Local similarity, if personal use shows the same bad groups repeating | Systematic missed groups or merged unrelated events during personal use | Medium | Not started |
| PROD-006 | In-process feed rank and search | A local index, if the feed gets slow or the order is systematically wrong | Slow feed or repeated ranking mistakes during personal use | Medium | Not started |
| PROD-007 | Review actions have no login | A local password before the API is reachable beyond this PC | API listens beyond localhost | High | Not started |
