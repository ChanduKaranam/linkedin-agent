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
**Session date:** 2026-05-27

**Changes made:**
- `routes_auth.py` — `login()` now returns `MeOut(user_id=user.user_id, username=user.username)` because `MeOut` schema now requires `user_id`.
- `routes_slack.py` — reordered `slack_publish_linkedin` params: `current_user` moved before `session` to fix Python syntax error (`non-default argument follows default argument`). `CurrentUser` is `Annotated[UserInfo, Depends(require_user)]` (no default), while `session` uses `= Depends(get_session)` (has default).

**Reason:** `MeOut.user_id` was added in refactoring but login was never updated to include it. The slack route had the wrong parameter order for FastAPI's Annotated dependency injection.

**Outcome:** Login now returns `{"user_id":3,"username":"ravi"}`. Slack publish endpoint compiles and imports without error.

**Watch out for:** Any other route that creates a `MeOut` must supply `user_id`. The `CurrentUser` type alias must always come before any `= Depends(...)` params in route signatures.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-27 | `routes_auth.py`, `routes_slack.py` | Fixed login MeOut to include user_id; fixed slack route param ordering |
| 2026-05-25 | `main.py` | Added Render keep-alive: `_keep_alive_loop()` self-pings `/ping` every 5 min; public `/ping` endpoint added; only activates when `RENDER` env var is set |
| 2026-05-08 | `main.py`, `routes_admin.py`, `routes_auth.py`, `routes_posts.py`, `routes_trends.py`, `routes_chat.py`, `schemas.py` | Full overhaul: DB log worker wiring, removed _guard(), OAuth nonce, 30-day cookies, smarter health endpoint, partial-trend run fix |
| 2026-05-07 | `main.py` | Added periodic stale-run cleanup (every 30 min) to auto-fail runs stuck in-progress for >2 hours |
| 2026-05-02 | `routes_trends.py` | Made /health a zero-DB liveness check to prevent "unreachable" during heavy pipeline runs |
| 2026-05-01 | `schemas.py`, `routes_posts.py` | Added GET /posts/all library endpoint; fixed _load_context to use slug-wide queries and 15 style samples; removed synchronous style profile refresh from hot path; raised generation timeouts to 120s |
| 2026-05-01 | `schemas.py`, `routes_posts.py` | Added `GeneratePostIn` schema; wired optional `user_instructions` into all four generate endpoints |
| 2026-04-29 | `main.py`, `schemas.py`, `routes_chat.py`, `routes_posts.py` (new) | Added Post Studio API: post generation, editing, LinkedIn publish, OAuth admin; wired style sample collection into chat routes |
| — | — | Initial documentation created |
