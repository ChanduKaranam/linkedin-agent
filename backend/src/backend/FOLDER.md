# backend/src/backend/

## Purpose
Core Python package. Implements the complete trend-intelligence system: configuration, data models, PostgreSQL + pgvector storage, 4-phase scraping pipeline, RAG indexing, AI agents (synthesis, chat, post writing), writing style learning, LinkedIn integration, REST API, and scheduler.

## Subfolders
| Folder | Role |
|---|---|
| `agent/` | LiteLLM agents — synthesis, chat (RAG), post writer |
| `api/` | FastAPI application and all REST route handlers |
| `rag/` | Chunk indexing and hybrid vector+BM25 retrieval |
| `style/` | User writing-style corpus collection and LLM-distilled profile |
| `integrations/` | LinkedIn OAuth 2.0 client and `/rest/posts` publisher |
| `scheduler/` | APScheduler daily job wrapper |

## Files in this Directory
| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `config.py` | `Settings` (reads `.env` — includes LinkedIn OAuth vars); `TopicConfig` from `topics.yaml`; sub-configs for Limits, Models, ChatBudget, Dedup |
| `models.py` | Pydantic domain models: `Source`, `DiscoveredUrl`, `ScrapedPage`, `Cluster`, `TrendSummary`, `DailyBriefs`, `PersistedTrend`, `RunState` |
| `db_models.py` | SQLAlchemy ORM models for all tables: `Run`, `Trend`, `ChatMessage`, `Insight`, `Chunk`, `StyleSample`, `StyleProfile`, `GeneratedPost`, `LinkedInAccount`, `AuthSession`, `User`, `LogEvent` |
| `db.py` | Async session factory (`get_session`) and engine lifecycle helpers. Pool: 5+10 connections, `pool_recycle=1800`. |
| `storage.py` | All DB CRUD. Includes `purge_old_logs`, `purge_expired_sessions`, `count_trends_for_run`, `get_log_events`, `get_available_dates` (now queries trends table directly). Style sample dedup via `text_hash`. |
| `pipeline.py` | 4-phase pipeline: Discover → Scrape → Synthesise → Persist + RAG index. Also `run_search_synthesis` for ad-hoc |
| `dedup.py` | `compute_fingerprint` + `deduplicate_urls` |
| `logging_setup.py` | DB-backed async structlog logging. `setup_logging()` + `start_log_worker()`/`stop_log_worker()`. Logs go to `log_events` table via async queue. 3rd-party noisy loggers silenced to WARNING. |

## Data Flow (pipeline.py)
```
Phase 1 — Discover:  search_web() per query → deduplicate_urls() → robots.txt filter
Phase 2 — Scrape:    scrape_url() with MD5-keyed file cache (cache_dir)
Phase 3 — Synthesise: synthesize_daily() — one LLM call for all articles
Phase 4 — Persist:   fingerprint_exists_in_window() dedup → upsert_trend()
```

## Last Session Changes
**Session date:** 2026-05-08

**Changes made:**
- `logging_setup.py` — full rewrite. Now routes all `backend.*` logs to a `log_events` Postgres table via an async queue (5000 cap, 200-row flush batches every 2s). Root logger capped at WARNING to silence httpx/playwright/litellm noise. `get_logger(name)` now prepends `backend.` if needed. `setup_logging()` + `start_log_worker()`/`stop_log_worker()` functions must be called from the app lifespan.
- `db_models.py` — added `LogEvent` ORM model (Phase 0). Updated `ChatMessage.run_id` → FK to `runs` (CASCADE), `Insight.run_id` → FK (SET NULL, now nullable), `GeneratedPost.run_id` → FK (SET NULL, now nullable). Added `AuthSession.expires_at` column. Added `StyleSample.text_hash` column + index. Added composite index on `GeneratedPost(kind, status, updated_at)` (Phase 3).
- `db.py` — reduced pool: `pool_size=5`, `max_overflow=10`, added `pool_recycle=1800`. Was overprovisioned at 10+20.
- `storage.py` — (Phase 0) `purge_old_logs`, `get_log_events`. (Phase 1) `_ip_timestamps` in routes_chat fixed separately. (Phase 3) `purge_expired_sessions`, `create_session` sets `expires_at`, `get_session_user` rejects expired sessions, `add_style_sample` deduplicates by `text_hash`, `update_run_state` truncates `last_error` to 2000 chars. `get_available_dates` now queries the `trends` table directly (not `runs`) so dates with partial/stuck runs still appear. Added `count_trends_for_run`.
- `config.py` — added `linkedin_token_key: str = ""` setting for Fernet-encrypted LinkedIn token storage.
- `pipeline.py` — robots.txt exceptions now disallow URLs (was accidentally allowing); `warnings` counter properly incremented on scrape failures and dedup skips so `completed_with_warnings` state triggers correctly.

**Reason:** This was a multi-phase overhaul: (Phase 0) agent.log was growing to ~1MB and had no expiry; (Phase 1) DB connection pool overprovisioned, event-loop blocking in retriever; (Phase 3) missing FKs meant orphan rows survived run deletion, auth sessions never expired, style samples could be duplicated; (Phase 4) LinkedIn tokens stored plaintext; (trends fix) `get_available_dates` used run state not trend existence, hiding today's 6 trends when the run was stuck at `summarizing`.

**Outcome:** All deployed. `backend/logs/agent.log` removed from git tracking — logs go to DB. Today's stuck run was fixed via `scripts/_fix_stuck_run.py`. Restart backend to apply logging changes.

**Watch out for:** `logging_setup.py` requires `start_log_worker()` to be awaited in `lifespan` before any log calls go to DB — during the brief window between `setup_logging()` and `start_log_worker()`, logs only go to stderr. The `add_style_sample` function now returns `None` on duplicate (was always returning `int`) — callers that checked the return value need updating if any. The `get_available_dates` change means a date with 0 trends in a stuck run no longer appears (good), but a date with trends in a `failed` run now DOES appear (also good).

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-08 | `logging_setup.py`, `db_models.py`, `db.py`, `storage.py`, `config.py`, `pipeline.py` | Full overhaul: DB log sink, FK constraints, auth session expiry, style dedup, LinkedIn token key setting, trends visibility fix |
| 2026-05-02 | `config.py`, `dedup.py`, `storage.py`, `pipeline.py` | Fixed 4 root causes of stale/duplicate trends: cache TTL, headline-only fingerprint, fuzzy cross-day dedup, recency filters |
| 2026-05-01 | `storage.py` | Added slug-wide insight/chat queries; rewrote list_all_generated_posts to avoid ORM outerjoin bug |
| 2026-04-29 | `config.py`, `db_models.py`, `storage.py` | Added LinkedIn OAuth config, 4 new ORM models, and all CRUD helpers for Post Studio + style learning |
| — | — | Initial documentation created |
