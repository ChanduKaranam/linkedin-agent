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
**Session date:** 2026-05-02

**Changes made:**
- `topics.yaml` — `dedup.cross_day_window` raised from `3` → `7`. With the fingerprint now headline-only and actually matching across days, a 7-day window meaningfully prevents the same story from resurfacing all week.
- `scripts/reset_today.py` — new utility script (new `scripts/` folder). Connects directly to the DB via SQLAlchemy, deletes today's daily run (cascade-deletes its trends/chunks), then fires a fresh pipeline run. Useful when you want to force a complete re-scrape of today's content. Must be run with `PYTHONUTF8=1` env var on Windows to avoid cp1252 encoding errors in structlog.

**Reason:** `cross_day_window=3` was too short once the fingerprint dedup started working; raised to 7 to cover a full week. The reset script was needed to manually delete stale/partial runs and immediately get fresh trends.

**Outcome:** `topics.yaml` updated. `scripts/reset_today.py` works — run as: `cd backend && PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/reset_today.py`

**Watch out for:** `reset_today.py` deletes ALL daily runs for today before starting a new one. It also runs the pipeline synchronously (blocking), which will take ~30 minutes due to RAG indexing. Do not use during production hours. The script uses the venv at `backend/.venv/` — use that Python, not system Python.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-02 | `topics.yaml`, `scripts/reset_today.py` (new) | Raised cross_day_window to 7; added reset script to delete today's run and re-trigger pipeline |
| 2026-04-29 | `.env.example`, `alembic/versions/0002_style_posts_linkedin.py` | Added LinkedIn OAuth env vars; new DB migration for style corpus + generated posts + LinkedIn account |
| 2026-04-29 | `FOLDER.md` | Initial creation — bootstrapping documentation system |
