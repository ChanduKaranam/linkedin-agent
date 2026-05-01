# backend/logs/

## Purpose
Runtime log directory. Contains structured JSON log files written by `structlog` via the `logging_setup.py` module. Git-ignored except for `.gitkeep`. The directory is auto-created by `config.py`.

## Files
| File | Purpose |
|---|---|
| `.gitkeep` | Ensures directory is tracked in git |
| `agent.log` | Main application log — newline-delimited JSON events from all modules |

## Log Format
Each line is a JSON object with fields:
- `timestamp` — ISO 8601
- `level` — INFO / WARNING / ERROR
- `event` — machine-readable event key (e.g. `"pipeline_complete"`, `"scrape_exception"`)
- Arbitrary extra fields per event (e.g. `run_id`, `url`, `error`)

## Last Session Changes
**Session date:** 2026-04-29

**Changes made:**
- `FOLDER.md` — created (this file) as part of the project-wide documentation system

**Reason:** Bootstrapping the `/start`+`/end` session-state skill infrastructure.

**Outcome:** Documentation complete. No log files were changed.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-04-29 | `FOLDER.md` | Initial creation — bootstrapping documentation system |
