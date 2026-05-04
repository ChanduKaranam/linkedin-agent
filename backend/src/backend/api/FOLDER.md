# backend/src/backend/api/

## Purpose
FastAPI application and route handlers. The `main.py` module creates the `app` instance, wires up middleware, mounts routers, and manages the startup/shutdown lifecycle (DB init, APScheduler, stale-run cleanup, catch-up run).

## Files
| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `main.py` | FastAPI `app` factory. Mounts all routers (trends, admin, search, chat, **posts**). CORS now includes `PATCH` method. |
| `schemas.py` | Pydantic request/response schemas. Includes `GeneratedPostOut`, `GeneratedPostPatchIn`, `LinkedInStatusOut`, `PublishResponseOut`, `GeneratePostIn`, `GeneratedPostListItem` (with `headline` field for the library endpoint). |
| `routes_trends.py` | `GET /trends/today`, `/trends/dates`, `/trends/by-date/{date}`, `/trends/{date}/{slug}` |
| `routes_search.py` | `POST /search`, `GET /search/history`, `GET /search/runs/{run_id}`, `GET /search/runs/{run_id}/trends`, `GET /search/runs/{run_id}/trends/{slug}` |
| `routes_chat.py` | Chat + insights endpoints. Calls `style.collector.record_sample()` on every user message and saved insight, and triggers async `refresh_profile_if_stale()` via `BackgroundTasks`. |
| `routes_posts.py` | Post generation, editing, publishing, and library listing. `GET /posts/all` **must be the first registered route** (before parameterized routes) to avoid FastAPI matching "all" as a path param. |
| `routes_admin.py` | `GET /admin/schedule`, `PUT /admin/schedule` |

## Critical Route Ordering in routes_posts.py
`GET /posts/all` is registered **first** in the file, before `GET /posts/{date}/{slug}`. This is mandatory — if placed after the parameterized route, FastAPI would match the literal path "all" as the `{date}` param and return a 400 validation error or wrong result.

## Windows-Specific Fixes (main.py top)
- `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` to handle Crawl4AI Unicode output on cp1252 consoles.
- `asyncio.WindowsProactorEventLoopPolicy()` to allow Playwright subprocess spawning by Crawl4AI.

## Scheduler Catch-up Logic
On server start, if the current local time is past today's scheduled time and no run exists for today, a catch-up run is immediately triggered as an `asyncio.create_task`.

## Last Session Changes
**Session date:** 2026-05-02

**Changes made:**
- `routes_trends.py` — `/health` endpoint no longer takes a `SessionDep` or calls `get_latest_completed_run`. It now returns `{"status": "ok", "latest_run_date": null, "trend_count": 0}` immediately with zero DB access. The `get_latest_completed_run` import was removed from this file.

**Reason:** The `/health` endpoint was timing out during pipeline runs because `get_latest_completed_run` needs a DB connection, and the RAG indexer (`embed_batch` via fastembed) was blocking the entire asyncio event loop with synchronous CPU work. The 5-second proxy timeout in `server.ts` fired before the health query could complete → frontend showed "Agent service is unreachable". Making health a pure liveness check (no DB) ensures it always responds instantly regardless of pipeline state.

**Outcome:** `/health` now responds in <5ms even while a full pipeline RAG index is running. The frontend "unreachable" banner disappears as soon as the backend is up, not just when it's idle. Date/trend information is still accurate via `/trends/dates` (which is fetched in parallel anyway).

**Watch out for:** The health response no longer includes a meaningful `latest_run_date` or `trend_count`. If any component relies on those fields from `/health` (rather than `/trends/dates`), it will always see `null`/`0`. Currently nothing in the frontend reads those fields — it only checks `healthRes.ok`.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-02 | `routes_trends.py` | Made /health a zero-DB liveness check to prevent "unreachable" during heavy pipeline runs |
| 2026-05-01 | `schemas.py`, `routes_posts.py` | Added GET /posts/all library endpoint; fixed _load_context to use slug-wide queries and 15 style samples; removed synchronous style profile refresh from hot path; raised generation timeouts to 120s |
| 2026-05-01 | `schemas.py`, `routes_posts.py` | Added `GeneratePostIn` schema; wired optional `user_instructions` into all four generate endpoints |
| 2026-04-29 | `main.py`, `schemas.py`, `routes_chat.py`, `routes_posts.py` (new) | Added Post Studio API: post generation, editing, LinkedIn publish, OAuth admin; wired style sample collection into chat routes |
| — | — | Initial documentation created |
