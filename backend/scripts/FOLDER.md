# backend/scripts/

## Purpose
One-off operational scripts for managing the backend outside of the normal API surface. These are run directly (not imported) by a developer when something needs manual intervention — resetting runs, seeding data, etc.

## Files
| File | Purpose |
|---|---|
| `reset_today.py` | Deletes today's daily run + cascade-deleted trends/chunks, then immediately fires a fresh pipeline run synchronously. Used when today's trends are stale, partial, or need a full re-scrape. |
| `fix_stuck_run.py` | One-off script used 2026-05-07 to mark a specific stuck `summarizing` daily run as `completed_with_warnings`. Hardcodes the affected `run_id`. **Do not re-run** — the run has already been fixed. Kept for reference only. |

## Usage
```bash
cd backend
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/reset_today.py
```

**Windows requirement:** The `PYTHONUTF8=1` env var is mandatory. Without it, structlog may hit a `UnicodeEncodeError` when logging scraped content with non-ASCII characters (cp1252 console codec). The script also reconfigures `sys.stdout`/`sys.stderr` to UTF-8 internally, but the env var must be set before Python starts for it to take effect on all paths.

## Last Session Changes
**Session date:** 2026-05-07

**Changes made:**
- `fix_stuck_run.py` — created. One-off script that connects directly to PostgreSQL via `asyncpg` and sets `state='completed_with_warnings'`, `finished_at=now()`, `trend_count=3`, `last_error='INTERRUPTED: pipeline got stuck at summarizing stage'` on the specific run `caf3aebe-3f5f-4be1-8cd7-481ccede072e`.

**Reason:** The frontend was showing "Pipeline is running — showing previous results" because a daily run got stuck in `summarizing` state at 06:10 UTC. The health endpoint saw this stuck `kind='daily'` run and reported `pipeline_running=true`. The correct fix was to mark it as `completed_with_warnings` so `get_latest_daily_run` returns it with priority=0, `pipeline_running=false`, and today's date appears in `/trends/dates`. (The alternatives were: mark as failed, losing visibility of the 3 partial trends; or restart the server, which also would have worked since `lifespan` cleanup runs on startup.)

**Outcome:** Script ran once, fixed the issue. Do not re-run. The run is now `completed_with_warnings` in the DB. Long-term prevention is handled by the new `_cleanup_stale_runs` scheduler job in `main.py`.

**Watch out for:** `fix_stuck_run.py` hardcodes a specific `run_id`. If a similar issue occurs in the future, use `reset_today.py` to fully reset and re-run, or adapt this script with the new `run_id`. The permanent fix (periodic stale-run cleanup) is now in `main.py`.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-07 | `fix_stuck_run.py` | One-off: marked stuck summarizing run as completed_with_warnings so frontend shows today's trends |
| 2026-05-02 | `reset_today.py` | Initial creation — manual pipeline reset utility |
