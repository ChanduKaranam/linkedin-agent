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
**Session date:** 2026-05-08

**Changes made:**
- `main.py` — Wired `start_log_worker()`/`stop_log_worker()` into `lifespan` (Phase 0 DB logging). Imported `count_trends_for_run`, `purge_expired_sessions`, `purge_old_logs`. Added `_catchup_task` ref with error callback (was fire-and-forget). Added `_resolve_stale_run()` helper: marks stuck runs `completed_with_warnings` if they produced trends, `failed` if not — both startup and periodic cleanups now use this. Added `purge_expired_sessions` to `_purge_old_data`.
- `routes_admin.py` — Removed `_guard()` function entirely (was blocking all admin endpoints when `DEBUG=false`). All admin routes are now accessible to any authenticated user. Added `GET /admin/logs` endpoint with level/logger/since/q/limit/offset filters. Added `LogEventOut` and `datetime` imports.
- `routes_auth.py` — Cookie `max_age` reduced from 10 years → 30 days (Phase 4 security).
- `routes_posts.py` — OAuth state nonce: `linkedin_authorize` now generates `secrets.token_urlsafe(32)`, stores it in an in-memory `_oauth_state` dict (10-min TTL, auto-eviction), and passes the nonce as `state`. `linkedin_callback` consumes and verifies the nonce — replayed or tampered callbacks are rejected with a warning log and redirect to `/`.
- `routes_trends.py` — `health` endpoint now smarter about `pipeline_running`: only reports `True` if the run is < 2 hours old AND has no trends yet. A run that has already persisted trends (but hasn't finished cleanly) no longer hides those trends from the frontend.
- `routes_chat.py` — `_ip_timestamps` memory leak fixed: replaced unbounded `defaultdict(deque)` with a bounded plain dict (max 5000 entries, LRU eviction of oldest IP).
- `schemas.py` — Added `LogEventOut` schema for the new `/admin/logs` endpoint.

**Reason:** (1) `_guard()` was blocking the schedule update and all admin routes in production (`DEBUG=false`). (2) DB logging needs the log worker wired into the app lifecycle. (3) The OAuth callback was using a path string as the `state` parameter — trivially forgeable. (4) Cookie lifetime of 10 years was excessive and inconsistent with the Phase 3 `expires_at` DB column. (5) Stale runs with partial trends were being marked `failed`, which hid their trends. (6) The health endpoint was hiding real trends when a run was merely stuck.

**Outcome:** All routes now accessible without `DEBUG=true`. Log worker starts/stops cleanly. OAuth flow is nonce-protected. Today's trends are visible even if the pipeline run was partial.

**Watch out for:** `_oauth_state` dict is in-memory and per-process — OAuth flows that span a server restart will fail (user sees redirect to `/` instead of their target page). This is acceptable for a single-user admin tool. The `_guard()` removal means `/admin/run-now` and `/admin/logs` are now accessible to all authenticated users — no separate "admin" role distinction yet. `routes_chat.py` IP eviction is LRU by insertion order (Python dict), so a specific IP won't see its window roll over mid-window.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-08 | `main.py`, `routes_admin.py`, `routes_auth.py`, `routes_posts.py`, `routes_trends.py`, `routes_chat.py`, `schemas.py` | Full overhaul: DB log worker wiring, removed _guard(), OAuth nonce, 30-day cookies, smarter health endpoint, partial-trend run fix |
| 2026-05-07 | `main.py` | Added periodic stale-run cleanup (every 30 min) to auto-fail runs stuck in-progress for >2 hours |
| 2026-05-02 | `routes_trends.py` | Made /health a zero-DB liveness check to prevent "unreachable" during heavy pipeline runs |
| 2026-05-01 | `schemas.py`, `routes_posts.py` | Added GET /posts/all library endpoint; fixed _load_context to use slug-wide queries and 15 style samples; removed synchronous style profile refresh from hot path; raised generation timeouts to 120s |
| 2026-05-01 | `schemas.py`, `routes_posts.py` | Added `GeneratePostIn` schema; wired optional `user_instructions` into all four generate endpoints |
| 2026-04-29 | `main.py`, `schemas.py`, `routes_chat.py`, `routes_posts.py` (new) | Added Post Studio API: post generation, editing, LinkedIn publish, OAuth admin; wired style sample collection into chat routes |
| — | — | Initial documentation created |
