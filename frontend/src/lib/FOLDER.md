# frontend/src/lib/

## Purpose
This folder holds lightweight frontend utility modules used across components and pages. It provides shared wrappers for backend HTTP requests, UI className composition helpers, and LinkedIn OAuth URL construction. Grouping these helpers here avoids duplicating small cross-cutting logic throughout feature components.

## Files
| File | Purpose |
|---|---|
| `api.ts` | Typed `fetch` helper functions for `GET`, `POST`, and `PATCH` with JSON handling, error normalization, and optional timeouts |
| `linkedinAuth.ts` | Builds the backend LinkedIn authorization endpoint URL with an encoded return path |
| `utils.ts` | Exposes `cn()` helper combining `clsx` + `tailwind-merge` for conditional Tailwind class composition |

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
