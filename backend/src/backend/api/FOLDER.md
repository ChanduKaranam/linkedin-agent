# backend/src/backend/api/

## Purpose
FastAPI application and route handlers. The `main.py` module creates the `app` instance, wires up middleware, mounts routers, and manages the startup/shutdown lifecycle (DB init, APScheduler, stale-run cleanup, catch-up run).

## Files
| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `main.py` | FastAPI `app` factory. Mounts all routers (trends, admin, search, chat, **posts**). CORS now includes `PATCH` method. |
| `schemas.py` | Pydantic request/response schemas. Now includes `GeneratedPostOut`, `GeneratedPostPatchIn`, `LinkedInStatusOut`, `PublishResponseOut`. |
| `routes_trends.py` | `GET /trends/today`, `/trends/dates`, `/trends/by-date/{date}`, `/trends/{date}/{slug}` |
| `routes_search.py` | `POST /search`, `GET /search/history`, `GET /search/runs/{run_id}`, `GET /search/runs/{run_id}/trends/{slug}` |
| `routes_chat.py` | Chat + insights endpoints. Now also calls `style.collector.record_sample()` on every user message and saved insight, and triggers async `refresh_profile_if_stale()` via `BackgroundTasks`. |
| `routes_posts.py` | **New.** `POST /posts/{date}/{slug}/linkedin|blog`, `GET /posts/{date}/{slug}`, `PATCH /posts/{post_id}`, `POST /posts/{post_id}/publish`. Also: `GET /admin/linkedin/status`, `GET /admin/linkedin/authorize`, `GET /admin/linkedin/callback`. Ad-hoc run variants at `/posts/runs/{run_id}/{slug}/*`. |
| `routes_admin.py` | `GET /admin/schedule`, `PUT /admin/schedule` |

## Windows-Specific Fixes (main.py top)
- `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` to handle Crawl4AI Unicode output on cp1252 consoles.
- `asyncio.WindowsProactorEventLoopPolicy()` to allow Playwright subprocess spawning by Crawl4AI.

## Scheduler Catch-up Logic
On server start, if the current local time is past today's scheduled time and no run exists for today, a catch-up run is immediately triggered as an `asyncio.create_task`.

## Last Session Changes
**Session date:** 2026-05-01

**Changes made:**
- `schemas.py` — added `GeneratePostIn` schema: `{ user_instructions: str = "" }` (max 2000 chars). Used as the optional request body for all four generate endpoints.
- `routes_posts.py` — updated all four generate endpoints (`POST /posts/{date}/{slug}/linkedin|blog` and `POST /posts/runs/{run_id}/{slug}/linkedin|blog`) to accept an optional `GeneratePostIn` body (default `GeneratePostIn()` so callers that send no body still work). The `user_instructions` string is passed through to `generate_linkedin_post()` / `generate_blog_post()`.

**Reason:** Users need to describe specific change requests when regenerating (e.g., "make the hook more provocative", "add more technical detail") without losing the full style context. The instruction is appended to the LLM user message as a `## Specific instructions for this version` section.

**Outcome:** Python syntax verified. Backwards-compatible — empty body and `{}` body both default to empty instructions, no breaking change for existing frontend callers.

**Watch out for:** FastAPI's default parameter for a `Body(...)` model must be set with `= GeneratePostIn()` on the function signature (not `Optional`), otherwise FastAPI will require the body even when it's empty. This pattern is correct in the current code.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-01 | `schemas.py`, `routes_posts.py` | Added `GeneratePostIn` schema; wired optional `user_instructions` into all four generate endpoints |
| 2026-04-29 | `main.py`, `schemas.py`, `routes_chat.py`, `routes_posts.py` (new) | Added Post Studio API: post generation, editing, LinkedIn publish, OAuth admin; wired style sample collection into chat routes |
| — | — | Initial documentation created |
