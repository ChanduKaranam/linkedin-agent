# backend/data/

## Purpose
Runtime data directory. Holds the SQLite database and the markdown scrape cache. Both are git-ignored (except `.gitkeep`). The directory is auto-created by `config.py` if it does not exist.

## Subfolders
| Folder | Role |
|---|---|
| `cache/` | Per-URL scrape cache — filename is `md5(url).md`, contains raw markdown of scraped page |

## Files
| File | Purpose |
|---|---|
| `.gitkeep` | Ensures the directory exists in git despite being otherwise empty |
| `trends.db` | SQLite database — tables: `runs`, `trends` (see `storage.py` for schema) |

## Database Schema Overview
**`runs` table** — one row per pipeline execution:
- `run_id` (UUID), `run_date`, `topic`, `kind` (daily/search), `state`, `started_at`, `finished_at`, `trend_count`, `warnings`, `last_error`

**`trends` table** — one row per synthesised story:
- `id`, `run_id`, `run_date`, `slug`, `headline`, `one_liner`, `detailed_markdown`, `key_points` (JSON), `sources` (JSON), `fingerprint`, `seen_again`, `created_at`

## Last Session Changes
**Session date:** 2026-04-29

**Changes made:**
- `FOLDER.md` — created (this file) as part of the project-wide documentation system

**Reason:** Bootstrapping the `/start`+`/end` session-state skill infrastructure.

**Outcome:** Documentation complete. No data files were changed.

**Watch out for:** `trends.db` and `cache/` are git-ignored. If the DB schema changes (in `storage.py`), update the "Database Schema Overview" section here.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-04-29 | `FOLDER.md` | Initial creation — bootstrapping documentation system |
