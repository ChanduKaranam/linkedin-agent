# ./

## Purpose
This repository contains the LinkedIn Agent system, which discovers trend sources, synthesizes insights, and helps generate/publish social posts. The backend runs the ingestion, RAG, scheduling, and publishing workflows, while the frontend provides an operator UI for trends, search, and post writing. The root exists to hold project-wide docs, ignore rules, and a small standalone model experiment script separate from production services. It is the coordination layer developers use to run and understand the full stack.

## Subfolders
| Folder | Role |
|---|---|
| `backend/` | FastAPI + pipeline backend, migrations, tests, and runtime data paths |
| `frontend/` | Vite + React application with Express proxy server and UI code |

## Files
| File | Purpose |
|---|---|
| `.gitignore` | Repository-wide ignore rules for env files, runtime data, build artifacts, and scratch files |
| `README.md` | End-to-end project guide: setup, architecture, pipeline flow, and operational instructions |
| `model.py` | Standalone Ollama prompt test script for bill-splitting JSON extraction (not part of main app runtime) |

## Last Session Changes
**Session date:** 2026-05-27

**Changes made:**
- New migration `0010_user_id_isolation.py` adds `user_id` column to all user-data tables and re-keys `users` table from username PK to `user_id` SERIAL PK.
- `routes_auth.py` — fixed `login()` to return `user_id` in `MeOut` (field became required).
- `routes_slack.py` — fixed `slack_publish_linkedin` parameter order (`current_user` before `session`) to avoid Python's non-default-after-default arg error.
- Migration was rewritten 3 times: first `autoincrement=True` failed (no sequence created), then raw SQL with `op.create_foreign_key` failed (PK not visible to alembic DDL), finally all-`op.execute()` raw SQL succeeded.
- All `user_id` columns backfilled: auth_sessions joined by username, other tables set to `MIN(user_id)`.
- `style_profile` and `linkedin_account` tables recreated with `user_id` as PK (old singleton rows migrated to first user).
- Users re-seeded: ravi (user_id=3), chandu (user_id=4), existing kiran (1) and admin (2) preserved.

**Reason:** Per-user data isolation — previously all users shared the same posts/chats/insights/style. Now each user has their own view. Trends remain shared.

**Outcome:** All endpoints tested and working: login, /me, /health, /trends/today, /trends/dates, /schedule, and session lifecycle.

**Watch out for:** Server takes ~60s to start due to slow ADK library import (pre-existing). `init_db()` runs `alembic upgrade head` via blocking `subprocess.run` which can cause Neon DB auth timeouts under frequent restarts.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-27 | `0010_user_id_isolation.py` (new), `routes_auth.py`, `routes_slack.py` | Added user_id SERIAL PK to users table + user_id FKs on all user-data tables; fixed MeOut login return; fixed slack route parameter order |
| 2026-05-06 | Initial creation | FOLDER.md bootstrapped by `/create` |
