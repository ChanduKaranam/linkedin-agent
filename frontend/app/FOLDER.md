# frontend/app/

## Purpose
Next.js App Router root. Contains the single-page application entry point (`page.tsx`), root layout, error/loading boundaries, and the full API proxy layer (under `api/`).

## Subfolders
| Folder | Role |
|---|---|
| `api/` | Next.js Route Handlers that proxy requests to the Python FastAPI backend |

## Files
| File | Purpose |
|---|---|
| `page.tsx` | Root page component — the entire UI. Manages state for: mode (daily/search), selected date, active trend slug, sidebar tab, search run. Fetches from `/api/*` routes on mount and on user interaction. |
| `layout.tsx` | Root HTML layout — sets `<html>` lang, loads global fonts, wraps children |
| `error.tsx` | React error boundary for unhandled render errors |
| `loading.tsx` | Suspense fallback shown while the root page hydrates |
| `globals.css` | Tailwind CSS base + component utilities |
| `favicon.ico` | Browser tab icon |

## page.tsx State Machine
```
backendStatus: "ok" | "unreachable" | "no_run"
mode:          "daily" | "search"
sidebarTab:    "trends" | "searches"

URL params kept in sync:
  ?d=YYYY-MM-DD   selected date
  ?t=<slug>       selected trend
```

## Last Session Changes
**Session date:** 2026-04-29

**Changes made:**
- `page.tsx` — added `postsApiBase`, `linkedinApiBase`, `blogApiBase` props to the `<SearchResultView>` render, deriving them from `searchRunId` and `searchBrief.slug`

**Reason:** `SearchResultView` now accepts Post Studio props and needs the run-specific API paths passed in from the parent page where `searchRunId` is stored in state.

**Outcome:** Works correctly. Daily trend PostStudio props are derived inside `TrendDetail` itself (from `trend.run_date` and `trend.slug`), so only the search-run variant needed wiring here.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-04-29 | `page.tsx` | Passed Post Studio API base props to SearchResultView for ad-hoc run post generation |
| — | — | Initial documentation created |
