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
| `0007_log_events.py` | `log_events` table for DB-backed structured logging. Indexes on `(ts)`, `(level, ts)`, `(logger_name, ts)`. |
| `0008_fk_indexes_retention.py` | FKs on `chat_messages.run_id` (CASCADE), `insights.run_id` (SET NULL), `generated_posts.run_id` (SET NULL). `auth_sessions.expires_at` column. `style_samples.text_hash` column. Composite index on `generated_posts(kind, status, updated_at)`. |
| `0009_style_chosen_eval.py` | Added `style_chosen` and `evaluation_json` to `generated_posts`. |
| `0010_user_id_isolation.py` | **New.** Adds `user_id` SERIAL PK to `users` table (was `username` PK). Adds `user_id` FK on `auth_sessions`, `chat_messages`, `insights`, `style_samples`, `generated_posts`, `runs`. Recreates `style_profile` and `linkedin_account` with `user_id` as PK. |

## Last Session Changes
**Session date:** 2026-05-27

**Changes made:**
- `0010_user_id_isolation.py` (new) — major migration adding `user_id` SERIAL PK to `users` table. Changes `users` PK from `username` to `user_id`. Adds `user_id` FK columns on `auth_sessions`, `chat_messages`, `insights`, `style_samples`, `generated_posts`, `runs`. Recreates `style_profile` and `linkedin_account` tables with `user_id` as PK (old singleton rows migrated to first user). Uses raw SQL for all DDL because alembic's `op.create_primary_key` and `op.create_foreign_key` methods had transaction-visibility issues where the PK wasn't visible when creating dependent FKs in the same transaction.

**Reason:** Per-user data isolation. The previous schema used `username` as the users PK, and all other tables had no user association.

**Outcome:** Migration applied successfully. Tested: login, /me, /health, /trends/today, /trends/dates, /schedule all return 200. Session lifecycle working.

**Watch out for:** The migration is idempotent (checks if `user_id` column exists before adding). Uses `op.execute()` with raw SQL for everything — no alembic DDL helpers. The sequence for `users.user_id` is named `users_user_id_seq`. The downgrade restores the old `username` PK and drops all `user_id` columns.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-27 | `0010_user_id_isolation.py` (new) | Added user_id SERIAL PK/isolation migration — users re-keyed, all user-data tables get user_id FKs |
| 2026-05-08 | `0007_log_events.py` (new), `0008_fk_indexes_retention.py` (new) | Added log_events table; FKs on chat/insight/post; auth session expiry; style sample text_hash |
| 2026-05-06 | Initial creation | FOLDER.md bootstrapped by `/create` |
