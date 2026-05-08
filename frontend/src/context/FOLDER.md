# frontend/src/context/

## Purpose
React Context providers for global state shared across the app. Four providers are stacked in `App.tsx` in this order (outermost first): WorkspaceProvider → BackendStatusProvider → SearchModeProvider → TimeProvider.

## Files
| File | Purpose |
|---|---|
| `WorkspaceContext.tsx` | `workspace: 'LINKEDIN_AGENT' | 'TILICHO_LABS'` + setter. Drives conditional rendering throughout the app. Default: `'LINKEDIN_AGENT'`. |
| `TimeContext.tsx` | `time: string` + setter. Displays in the Navbar's mono clock chip. Set via the "Set Timer" modal. Not used by any page logic. |
| `BackendStatusContext.tsx` | **New.** Bootstraps on mount: `Promise.all([/api/health, /api/trends/dates, /api/admin/schedule])`. Exposes `backendStatus`, `schedule`, `availableDates`, `selectedDate`, `setSelectedDate`, `setSchedule`, `refresh()`. Consumed by Trends, BlogPost, LinkedInPost, NewPostDialog, Insights. |
| `SearchModeContext.tsx` | **New.** Manages `mode: 'daily' | 'search'`, `searchTopic`, `searchRunId`, `searchTrends`, `searchBrief`. `enterSearch()` fetches the first trend's detail. `clearSearch()` resets state and removes `?q=` from the URL. Shared between Trends and Searches pages. |

## Last Session Changes
**Session date:** 2026-05-08

**Changes made:**
- `BackendStatusContext.tsx` — rewrote the polling logic. (1) Polling now pauses when `document.visibilityState === 'hidden'` and resumes immediately on `visibilitychange`. (2) Consecutive failures trigger exponential backoff: 15s → 30s → 60s (cap), so a downed backend doesn't hammer the proxy. (3) Used `useRef` for `consecutiveFailures` to avoid poll-interval reset on every failure count change. (4) Added `visibilitychange` listener that calls `bootstrap()` on tab focus.

**Reason:** The previous interval-based polling (`setInterval`) ran constantly even when the tab was hidden, wasting network requests. On consecutive backend failures (503, network error), it kept polling at 5s or 15s — a problem if the backend was intentionally stopped. A downed Vercel deployment would result in repeated failed requests.

**Outcome:** Tab-hidden polling pause is working. Backoff tested manually (close backend, watch intervals grow). The `visibilitychange` immediate refresh means users coming back to a hidden tab see fresh data without waiting for the next poll interval.

**Watch out for:** The `scheduleNext()` recursive timeout pattern means only one poll is ever queued at a time — there's no risk of multiple concurrent polls stacking up. However, the timeout ID is NOT stored globally, so calling `bootstrap()` manually (via `refresh()`) doesn't cancel a pending scheduled poll. This is acceptable since polls are idempotent.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-08 | `BackendStatusContext.tsx` | Added visibility gating + exponential backoff on consecutive failures to reduce unnecessary polling |
| 2026-05-01 | `BackendStatusContext.tsx` (new), `SearchModeContext.tsx` (new) | Created backend bootstrap context and search mode context for multi-page Vite architecture |
| 2026-05-01 | `WorkspaceContext.tsx`, `TimeContext.tsx` | Ported unchanged from next-fe/ prototype |
