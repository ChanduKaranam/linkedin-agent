# backend/alembic/versions/

## Purpose
This folder stores the concrete Alembic revision scripts that define database schema history for the backend. Each file is an ordered migration step applied by `alembic upgrade head`, including pgvector setup, core trend tables, and post-style/linkedin persistence tables. Keeping this folder separate preserves deterministic schema evolution across environments.

## Files
| File | Purpose |
|---|---|
| `0001_init.py` | Initial schema: `runs`, `trends`, `chat_messages`, `insights`, `chunks` + pgvector/TSV indexes |
| `0002_style_posts_linkedin.py` | Style corpus, generated posts, LinkedIn account token tables |
| `0003_linkedin_member_name.py` | Added `member_name` column to `linkedin_account` |
| `0004_post_headline_retention.py` | Added `headline` to `generated_posts`; run retention column |
| `0005_headline_server_default.py` | Server default for `generated_posts.headline` |
| `0006_users_and_sessions.py` | `users` + `auth_sessions` tables (username/password + session token) |
| `0007_log_events.py` | **New.** `log_events` table for DB-backed structured logging. Indexes on `(ts)`, `(level, ts)`, `(logger_name, ts)`. |
| `0008_fk_indexes_retention.py` | **New.** FKs on `chat_messages.run_id` (CASCADE), `insights.run_id` (SET NULL), `generated_posts.run_id` (SET NULL). `auth_sessions.expires_at` column. `style_samples.text_hash` column. Composite index on `generated_posts(kind, status, updated_at)`. |

## Last Session Changes
**Session date:** 2026-05-08

**Changes made:**
- `0007_log_events.py` — new migration creating the `log_events` table (id, ts, level, logger_name, event, message, data JSONB, run_id). Three indexes for efficient filtering. Idempotent: skips if table exists.
- `0008_fk_indexes_retention.py` — new migration adding FKs with cascade behavior, `auth_sessions.expires_at`, `style_samples.text_hash`, and a composite index. Handles orphan rows before adding constraints (nulls out or deletes orphans). Backfills `expires_at` from `last_seen_at + 30 days` for existing sessions. Backfills `text_hash` via `md5(text)` for existing style samples.

**Reason:** Phase 0: agent.log was growing unboundedly — moved to DB with retention. Phase 3: missing FKs allowed orphan rows when runs were deleted; auth sessions had no expiry; style samples had no deduplication.

**Outcome:** Both migrations are idempotent and safe to re-run. Applied automatically on next server start via `alembic upgrade head` in `init_db()`.

**Watch out for:** `0008` uses raw `text()` SQL to backfill data (not ORM). The `alter_column nullable=True` for `insights.run_id` and `generated_posts.run_id` may fail if the DB already has a `NOT NULL` constraint with a name — the migration uses `op.alter_column` which handles this on Postgres. On other DBs, manual intervention may be needed.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-08 | `0007_log_events.py` (new), `0008_fk_indexes_retention.py` (new) | Added log_events table; FKs on chat/insight/post; auth session expiry; style sample text_hash |
| 2026-05-06 | Initial creation | FOLDER.md bootstrapped by `/create` |
