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
| `alembic/` | Database migrations (0001 = core tables, 0002 = style/posts/LinkedIn tables) |

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
**Session date:** 2026-04-29

**Changes made:**
- `.env.example` — added three LinkedIn OAuth variables: `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI`
- `alembic/versions/0002_style_posts_linkedin.py` — new migration creating `style_samples`, `style_profile`, `generated_posts`, `linkedin_account` tables

**Reason:** Post Studio feature added. Users can now generate LinkedIn posts and blog drafts from their chat sessions, and publish directly to LinkedIn. Style learning requires new DB tables for the corpus and distilled profile.

**Outcome:** Migration file is ready. Run `alembic upgrade head` to apply. LinkedIn OAuth requires a Developer App to be registered at linkedin.com/developers/apps — see README.

**Watch out for:** `topics.yaml` controls both the schedule and the search queries. The database is now PostgreSQL (not SQLite) — ensure `DATABASE_URL` in `.env` points at a running Postgres instance with the `vector` extension installed.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-04-29 | `.env.example`, `alembic/versions/0002_style_posts_linkedin.py` | Added LinkedIn OAuth env vars; new DB migration for style corpus + generated posts + LinkedIn account |
| 2026-04-29 | `FOLDER.md` | Initial creation — bootstrapping documentation system |
