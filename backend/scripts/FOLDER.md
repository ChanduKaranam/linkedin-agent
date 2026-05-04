# backend/scripts/

## Purpose
One-off operational scripts for managing the backend outside of the normal API surface. These are run directly (not imported) by a developer when something needs manual intervention — resetting runs, seeding data, etc.

## Files
| File | Purpose |
|---|---|
| `reset_today.py` | Deletes today's daily run + cascade-deleted trends/chunks, then immediately fires a fresh pipeline run synchronously. Used when today's trends are stale, partial, or need a full re-scrape. |

## Usage
```bash
cd backend
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/reset_today.py
```

**Windows requirement:** The `PYTHONUTF8=1` env var is mandatory. Without it, structlog may hit a `UnicodeEncodeError` when logging scraped content with non-ASCII characters (cp1252 console codec). The script also reconfigures `sys.stdout`/`sys.stderr` to UTF-8 internally, but the env var must be set before Python starts for it to take effect on all paths.

## Last Session Changes
**Session date:** 2026-05-02

**Changes made:**
- `reset_today.py` — created. Connects to the DB using the same `Settings`/`TopicConfig` as the backend. Deletes all `daily` `Run` rows for today (cascade-deletes `Trend` and `Chunk` rows). Creates a fresh `Run` and calls `run_pipeline_safe` synchronously. Prints progress to stdout.

**Reason:** During development, today's pipeline run may be partial (crashed mid-index), stale (old cached content), or need a complete redo after config changes. The API's `POST /admin/run-now?force=true` only overwrites the run record — it doesn't wait for completion and can't be called when the backend is unreachable. A direct script was needed.

**Outcome:** Script works. Caveat: if the pipeline fails partway through with a Unicode error, re-run with explicit `PYTHONUTF8=1`. The pipeline takes ~30 minutes due to RAG indexing (828 chunks × 9 trends). Do not run while the backend is serving traffic — the synchronous pipeline will not block the backend's event loop (the event loop isn't involved), but it does consume significant CPU for fastembed inference.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-02 | `reset_today.py` | Initial creation — manual pipeline reset utility |
