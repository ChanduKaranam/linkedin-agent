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
| `config.py` | `Settings` (reads `.env` — now includes LinkedIn OAuth vars); `TopicConfig` from `topics.yaml`; sub-configs for Limits, Models, ChatBudget, Dedup |
| `models.py` | Pydantic domain models: `Source`, `DiscoveredUrl`, `ScrapedPage`, `Cluster`, `TrendSummary`, `DailyBriefs`, `PersistedTrend`, `RunState` |
| `db_models.py` | SQLAlchemy ORM models for all 8 tables: `Run`, `Trend`, `ChatMessage`, `Insight`, `Chunk`, `StyleSample`, `StyleProfile`, `GeneratedPost`, `LinkedInAccount` |
| `db.py` | Async session factory (`get_session`) and engine lifecycle helpers |
| `storage.py` | All DB CRUD: runs, trends, chat messages, insights, style samples, style profile, generated posts, LinkedIn account |
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
**Session date:** 2026-04-29

**Changes made:**
- `config.py` — added `linkedin_client_id`, `linkedin_client_secret`, `linkedin_redirect_uri` fields to `Settings`
- `db_models.py` — added `StyleSample`, `StyleProfile`, `GeneratedPost`, `LinkedInAccount` ORM models
- `storage.py` — added CRUD helpers for all 4 new tables (style samples, style profile, generated posts, LinkedIn account); updated import line to include new models

**Reason:** Post Studio feature — LinkedIn post and blog generation with adaptive style learning.

**Outcome:** All models and storage helpers in place. Migration 0002 creates the corresponding tables. `httpx` (already in requirements) is used by `integrations/linkedin.py` for OAuth token exchange and post publishing.

**Watch out for:** `storage.py` is now long (~550 lines). If adding more tables, consider splitting into `storage_chat.py`, `storage_posts.py` etc. The `_orm_to_post` and `_orm_to_run` helpers follow the same pattern — keep consistent.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-04-29 | `config.py`, `db_models.py`, `storage.py` | Added LinkedIn OAuth config, 4 new ORM models, and all CRUD helpers for Post Studio + style learning |
| — | — | Initial documentation created |
