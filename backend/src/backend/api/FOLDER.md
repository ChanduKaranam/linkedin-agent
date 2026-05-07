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
**Session date:** 2026-05-07

**Changes made:**
- `main.py` — Added `_cleanup_stale_runs()` async function and `_STALE_RUN_TIMEOUT_HOURS = 2` constant. The function queries `get_stale_runs()` and marks any in-progress run whose `started_at` is older than 2 hours as `failed` with error `"TIMEOUT: run exceeded 2-hour limit"`. Wired it into APScheduler as an `interval` job running every 30 minutes (`id="stale_run_cleanup"`). Also added `timedelta` and `timezone` to the `datetime` import.

**Reason:** A daily scheduler run got stuck at `summarizing` state (LLM timeout mid-pipeline), and the stale-run cleanup in `lifespan` only fires on server startup — not for runs that get stuck while the server is already running. The stuck run caused the frontend to show "Pipeline is running — showing previous results" indefinitely, even though today's completed trends existed (from a separate adhoc run). The periodic cleanup ensures future stuck runs are auto-resolved within 2 hours without needing a manual DB fix or server restart.

**Outcome:** Working. The scheduler job is registered at startup when `ENABLE_INPROCESS_SCHEDULER=true`. Stale run cleanup now happens both at startup (existing logic) and every 30 minutes during operation (new job).

**Watch out for:** The cleanup marks runs `failed`, not `completed_with_warnings` — even if those runs produced partial trends before hanging. Trends already written to the DB for a timed-out run remain accessible via `get_trends_for_date` (queried by run_date, not run_id) but the run itself will appear as failed in the history. If partial results are valuable, the run state could be changed to `completed_with_warnings` instead — but that requires knowing how many trends were saved.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-07 | `main.py` | Added periodic stale-run cleanup (every 30 min) to auto-fail runs stuck in-progress for >2 hours |
| 2026-05-02 | `routes_trends.py` | Made /health a zero-DB liveness check to prevent "unreachable" during heavy pipeline runs |
| 2026-05-01 | `schemas.py`, `routes_posts.py` | Added GET /posts/all library endpoint; fixed _load_context to use slug-wide queries and 15 style samples; removed synchronous style profile refresh from hot path; raised generation timeouts to 120s |
| 2026-05-01 | `schemas.py`, `routes_posts.py` | Added `GeneratePostIn` schema; wired optional `user_instructions` into all four generate endpoints |
| 2026-04-29 | `main.py`, `schemas.py`, `routes_chat.py`, `routes_posts.py` (new) | Added Post Studio API: post generation, editing, LinkedIn publish, OAuth admin; wired style sample collection into chat routes |
| — | — | Initial documentation created |
