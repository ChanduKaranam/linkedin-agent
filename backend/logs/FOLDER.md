# backend/logs/

## Purpose
Runtime log directory. Previously held `agent.log` (newline-delimited JSON written by structlog). As of 2026-05-08, logs are written to the `log_events` Postgres table instead of a file. This directory is now empty except for `.gitkeep`. The stderr stream handler still exists in dev mode for tail-friendly local output.

## Files
| File | Purpose |
|---|---|
| `.gitkeep` | Ensures directory is tracked in git |

## Log Access
Logs are now queryable via `GET /admin/logs` (requires auth). Params: `level`, `logger`, `since` (ISO timestamp), `q` (substring), `limit` (≤500), `offset`. Retention: INFO/DEBUG rows purged after 7 days; WARNING/ERROR/CRITICAL after 30 days. Purge runs daily as part of `_purge_old_data()`.

## Last Session Changes
**Session date:** 2026-05-08

**Changes made:**
- `agent.log` — removed from git tracking (`git rm --cached backend/logs/agent.log`). The file itself still exists locally but is gitignored via `backend/logs/` in `.gitignore`.
- Logging architecture changed: `logging_setup.py` rewritten to route all `backend.*` logs to `log_events` Postgres table via async queue. File handler removed entirely. 3rd-party loggers (httpx, playwright, litellm, ddgs) silenced to WARNING to stop polluting the log stream.

**Reason:** `agent.log` was growing to ~1MB with no time-based expiry. The file contained a mix of structured JSON from our code and raw HTTP trace lines from 3rd-party libraries. Moving to DB gives: time-based retention, queryable via API, no unbounded disk usage, consistent structured format.

**Outcome:** `agent.log` no longer written to. Logs visible at `GET /admin/logs` after backend restart. Existing log content in the file is not migrated (historical logs are gone — this is acceptable).

**Watch out for:** If the DB is unreachable at startup, `start_log_worker()` still runs but the flush worker will print errors to stderr and drop log records. This is intentional fail-safe behavior — logging failure should never crash the app. Check stderr output if logs aren't appearing in the DB.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-08 | `agent.log` removed from git | Moved logging from file to DB (log_events table); file handler eliminated |
| 2026-04-29 | `FOLDER.md` | Initial creation — bootstrapping documentation system |
