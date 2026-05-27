# backend/

## Purpose
Python backend server built with FastAPI. Orchestrates the full trend-intelligence pipeline: web discovery via Tavily/DuckDuckGo, page scraping via Crawl4AI, LLM synthesis via LiteLLM (Mistral), RAG indexing with pgvector, and persistence to PostgreSQL. Exposes a REST API consumed by the Next.js frontend. Also handles LinkedIn OAuth and post publishing.

## Subfolders
| Folder | Role |
|---|---|
| `src/` | All importable Python source code |
| `data/` | Runtime data: SQLite database (`trends.db`) and MD-file scrape cache |
| `logs/` | Structured JSON log files written by `structlog` |
| `tests/` | Pytest unit and integration test suite |

## Key Files
| File | Purpose |
|---|---|
| `run.py` | Entry point — `uvicorn backend.api.main:app` with hot-reload |
| `pyproject.toml` | Package metadata, tool config (pytest, ruff, mypy) |
| `requirements.txt` | Production dependencies |
| `requirements-dev.txt` | Development-only dependencies (pytest, ruff, etc.) |
| `.env` | Local secrets — never committed |
| `.env.example` | Template for `.env` (includes LinkedIn OAuth vars as of 2026-04-29) |
| `topics.yaml` | Topic definition: search queries, schedule time, model choices, rate limits |
| `alembic.ini` | Alembic configuration pointing at `alembic/` |
| `alembic/` | Database migrations (0001 = core tables, 0010 = user_id isolation) |

## topics.yaml Structure
```yaml
topic: "AI in LinkedIn"
schedule_hour: 4
schedule_minute: 0
timezone: "Asia/Kolkata"
queries:
  - "AI LinkedIn trends"
  - ...
limits:
  max_sources_per_run: 30
  max_per_query: 10
  scrape_concurrency: 4
models:
  cluster: "mistral/mistral-small-latest"
  summarize: "mistral/mistral-small-latest"
```

## Last Session Changes
**Session date:** 2026-05-27

**Changes made:**
- `alembic/versions/0010_user_id_isolation.py` (new) — migration adding `user_id` SERIAL PK to `users` table (was `username` PK), and `user_id` FK columns on `auth_sessions`, `chat_messages`, `insights`, `style_samples`, `generated_posts`, and `runs`. Recreates `style_profile` and `linkedin_account` tables with `user_id` as PK. Uses raw SQL throughout (alembic DDL helpers had transaction-visibility issues).
- `src/backend/api/routes_auth.py` — `login()` now returns `user_id` alongside `username` in `MeOut`.
- `src/backend/api/routes_slack.py` — reordered `slack_publish_linkedin` params so `current_user` comes before `session` to satisfy Python's non-default-after-default rule.

**Reason:** Per-user data isolation. Previously all users shared the same posts, chats, insights, style profiles, and LinkedIn accounts. Now each user gets their own view; trends remain shared.

**Outcome:** Migration 0010 applied successfully at revision 0010 (head). Users (ravi, chandu, kiran, admin) have sequential user_ids 1-4. All protected endpoints (login, /me, /health, /trends/today, /schedule) tested and returning 200. Session lifecycle (login → me → logout → me 401) working.

**Watch out for:** Server takes ~60s to start due to slow ADK library import. Neon DB connection rate-limited under frequent restarts.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-27 | `alembic/versions/0010_user_id_isolation.py` (new), `routes_auth.py`, `routes_slack.py` | Added user_id PK/FK migration; fixed login MeOut; fixed slack route param order |
| 2026-05-02 | `topics.yaml`, `scripts/reset_today.py` (new) | Raised cross_day_window to 7; added reset script to delete today's run and re-trigger pipeline |
| 2026-04-29 | `.env.example`, `alembic/versions/0002_style_posts_linkedin.py` | Added LinkedIn OAuth env vars; new DB migration for style corpus + generated posts + LinkedIn account |
| 2026-04-29 | `FOLDER.md` | Initial creation — bootstrapping documentation system |
