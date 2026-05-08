# backend/scripts/

## Purpose
One-off operational scripts for managing the backend outside of the normal API surface. These are run directly (not imported) by a developer when something needs manual intervention — resetting runs, seeding data, etc.

## Files
| File | Purpose |
|---|---|
| `reset_today.py` | Deletes today's daily run + cascade-deleted trends/chunks, then immediately fires a fresh pipeline run synchronously. Used when today's trends are stale or need a full re-scrape. |
| `seed_user.py` | Inserts or updates a user in the `users` table with a hashed password. Usage: `python scripts/seed_user.py <username>` — password is read via `getpass` (not a CLI arg). |
| `_check_db.py` | Read-only diagnostic: prints recent runs, trend counts for today, and available trend dates. Safe to re-run at any time. |
| `_fix_stuck_run.py` | Fixes any run stuck in a non-terminal state: marks it `completed_with_warnings` if it has trends, `failed` if not. Re-runnable. Supersedes the old hardcoded `fix_stuck_run.py`. |

## Usage
```bash
cd backend
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/reset_today.py
```

**Windows requirement:** The `PYTHONUTF8=1` env var is mandatory. Without it, structlog may hit a `UnicodeEncodeError` when logging scraped content with non-ASCII characters (cp1252 console codec). The script also reconfigures `sys.stdout`/`sys.stderr` to UTF-8 internally, but the env var must be set before Python starts for it to take effect on all paths.

## Last Session Changes
**Session date:** 2026-05-08

**Changes made:**
- `seed_user.py` — changed password input from CLI positional arg (`sys.argv[2]`) to `getpass.getpass()`. This prevents the password from appearing in shell history and `ps` output.
- `_check_db.py` — new diagnostic script. Connects to the DB, prints today's runs with state/trend counts, and shows available trend dates. Uses `src.backend.config` so it respects `.env`.
- `_fix_stuck_run.py` — new reusable stuck-run fixer. Queries all non-terminal runs, checks each for existing trends via `COUNT(*)`, marks `completed_with_warnings` (with correct `trend_count`) or `failed` as appropriate. **Used today to fix a run stuck at `summarizing` with 6 trends already in the DB.**

**Reason:** Today's trends weren't showing in the frontend. The pipeline had produced 6 trends but crashed before calling `update_run_state("completed")`, leaving the run stuck at `summarizing` with `trend_count=0`. The old `fix_stuck_run.py` was hardcoded to a specific run_id; the new `_fix_stuck_run.py` is generic and re-runnable. `seed_user.py` was leaking passwords to shell history.

**Outcome:** `_fix_stuck_run.py` ran and fixed the stuck run (now `completed_with_warnings`, `trend_count=6`). Today's trends are now visible. The systemic fix (smarter health endpoint + `get_available_dates` from trends table) is in `routes_trends.py` and `storage.py`.

**Watch out for:** `_check_db.py` and `_fix_stuck_run.py` use raw `text()` SQL with f-string formatting — safe only because they only select from known tables. Do not pass user input into these scripts. Run from `backend/` directory: `PYTHONUTF8=1 python scripts/_fix_stuck_run.py`.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-08 | `seed_user.py`, `_check_db.py` (new), `_fix_stuck_run.py` (new) | getpass for seed_user; generic stuck-run fixer used to resolve today's stuck summarizing run |
| 2026-05-07 | `fix_stuck_run.py` | One-off: marked stuck summarizing run as completed_with_warnings so frontend shows today's trends |
| 2026-05-02 | `reset_today.py` | Initial creation — manual pipeline reset utility |
