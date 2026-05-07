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
