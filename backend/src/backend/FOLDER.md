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
| `db_models.py` | SQLAlchemy ORM models for all tables: `Run`, `Trend`, `ChatMessage`, `Insight`, `Chunk`, `StyleSample`, `StyleProfile`, `GeneratedPost`, `LinkedInAccount` |
| `db.py` | Async session factory (`get_session`) and engine lifecycle helpers |
| `storage.py` | All DB CRUD: runs, trends, chat messages, insights, style samples, style profile, generated posts, LinkedIn account. Includes slug-wide insight/chat queries for post context. |
| `pipeline.py` | 4-phase pipeline: Discover → Scrape → Synthesise → Persist + RAG index. Also `run_search_synthesis` for ad-hoc |
| `dedup.py` | `compute_fingerprint` + `deduplicate_urls` |
| `logging_setup.py` | `structlog` JSON logging; `get_logger()` factory |

## Data Flow (pipeline.py)
```
Phase 1 — Discover:  search_web() per query → deduplicate_urls() → robots.txt filter
Phase 2 — Scrape:    scrape_url() with MD5-keyed file cache (cache_dir)
Phase 3 — Synthesise: synthesize_daily() — one LLM call for all articles
Phase 4 — Persist:   fingerprint_exists_in_window() dedup → upsert_trend()
```

## Last Session Changes
**Session date:** 2026-05-02

**Changes made:**
- `config.py` — added `cache_ttl_hours: int = 18` to `Limits`. Scrape cache files older than this are deleted and re-scraped on next hit.
- `dedup.py` — `compute_fingerprint` is now **headline-only** (was `headline + all_sources`). Removed the `sources` parameter entirely and the `Source` import. Old fingerprints in the DB are now incompatible but harmless — the dedup window only looks back N days.
- `storage.py` — added `get_recent_headlines(session, window_days) -> list[str]`: returns all trend headlines from the last N days. Used by pipeline for fuzzy cross-day dedup.
- `pipeline.py` — (1) both `_scrape_one` functions now check `cache_file.stat().st_mtime` and skip cache if file is older than `limits.cache_ttl_hours`; (2) both `compute_fingerprint` calls updated to drop the now-removed `sources` arg; (3) daily pipeline now fetches `recent_headlines` before the persist loop and skips any trend with ≥80% fuzzy similarity to a recent headline. Added `import time` at the top.

**Reason:** Four root causes of stale/duplicate trends fixed: (A) scrape cache never expired so weeks-old content was fed to LLM; (B) fingerprint used all-run sources so same story had different fingerprint each day — cross-day dedup never fired; (C) no semantic similarity check meant reworded versions of the same story got through; (D) DuckDuckGo had no date filter.

**Outcome:** All fixes deployed. The `cross_day_window` in `topics.yaml` was raised from 3 → 7 days to take advantage of the now-working fingerprint dedup. Watch out for: old cached `.md` files in `backend/data/cache/` will be re-scraped on first access past their TTL — this is intentional.

**Watch out for:** `compute_fingerprint` signature changed — any external callers (tests, scripts) that passed a `sources` list will break. `test_dedup.py` was already updated.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-02 | `config.py`, `dedup.py`, `storage.py`, `pipeline.py` | Fixed 4 root causes of stale/duplicate trends: cache TTL, headline-only fingerprint, fuzzy cross-day dedup, recency filters |
| 2026-05-01 | `storage.py` | Added slug-wide insight/chat queries; rewrote list_all_generated_posts to avoid ORM outerjoin bug |
| 2026-04-29 | `config.py`, `db_models.py`, `storage.py` | Added LinkedIn OAuth config, 4 new ORM models, and all CRUD helpers for Post Studio + style learning |
| — | — | Initial documentation created |
