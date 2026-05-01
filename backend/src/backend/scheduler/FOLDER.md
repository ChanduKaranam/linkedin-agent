# backend/src/backend/scheduler/

## Purpose
APScheduler integration for the daily pipeline job. The in-process scheduler is optional — it is enabled when `ENABLE_INPROCESS_SCHEDULER=true` in `.env`. In production the daily job may instead be triggered externally (cron, systemd timer, etc.).

## Files
| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `daily_job.py` | Standalone job runner that can be invoked directly (e.g. `python -m backend.scheduler.daily_job`) without starting the HTTP server. Used for testing the pipeline outside FastAPI. |

## Last Session Changes
_No changes recorded yet. Run `/end` at session close to record changes._

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| — | — | Initial documentation created |
