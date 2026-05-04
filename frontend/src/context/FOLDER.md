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
**Session date:** 2026-05-01

**Changes made:**
- `BackendStatusContext.tsx` — created. Replaces the bootstrap logic that was inline in the old Next.js `page.tsx`. Handles health-check → date loading → schedule loading in one `Promise.all`.
- `SearchModeContext.tsx` — created. Replaces the search mode state that was inline in the old `page.tsx`. Allows Trends and Searches pages to share one source of truth for active search.

**Reason:** In the old Next.js app, all app-level state lived in a single `page.tsx` component. The Vite multi-page architecture needs explicit context providers to share state across routes.

**Outcome:** Both contexts working correctly. Backend status drives empty states across all pages.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-01 | `BackendStatusContext.tsx` (new), `SearchModeContext.tsx` (new) | Created backend bootstrap context and search mode context for multi-page Vite architecture |
| 2026-05-01 | `WorkspaceContext.tsx`, `TimeContext.tsx` | Ported unchanged from next-fe/ prototype |
