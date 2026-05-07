# backend/alembic/versions/

## Purpose
This folder stores the concrete Alembic revision scripts that define database schema history for the backend. Each file is an ordered migration step applied by `alembic upgrade head`, including pgvector setup, core trend tables, and post-style/linkedin persistence tables. Keeping this folder separate preserves deterministic schema evolution across environments.

## Files
| File | Purpose |
|---|---|
| `0001_init.py` | Initial schema migration creating core pipeline/RAG tables (`runs`, `trends`, `chat_messages`, `insights`, `chunks`) plus vector and TSV indexes/triggers |
| `0002_style_posts_linkedin.py` | Follow-up migration adding style corpus, generated post storage, and LinkedIn account token tables |

## Last Session Changes
**Session date:** 2026-05-06

**Changes made:**
- FOLDER.md created by `/create` — initial documentation pass.

**Reason:** Bootstrapping project documentation so that `/start` and `/end` can be used going forward.

**Outcome:** Complete — all files documented as of this date.

**Watch out for:** This documentation was generated from a static read of the code. If any files have changed since this was written, run `/end` after your next session to keep it current.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-06 | Initial creation | FOLDER.md bootstrapped by `/create` |
