# frontend/src/pages/

## Purpose
One component per route. LinkedIn workspace pages are wired to the backend. Tilicho workspace pages (`InternalUpdates`, `SlackPost`) keep mock data with a "TILICHO · COMING SOON" badge.

## Files
| File | Purpose |
|---|---|
| `Trends.tsx` | Daily trend browser. Three-pane: DateSelector → TrendList (left) → TrendDetail (right). LinkedIn workspace wired to backend; Tilicho shows mock headlines. Reads `BackendStatusContext` for empty states. Syncs `?d=` and `?t=` URL params. |
| `Searches.tsx` | On-demand research. Left: SearchHistory. Right: SearchBar + SearchResultView when results exist. Tilicho workspace shows mock experiment history with Coming Soon badge. Uses `SearchModeContext`. |
| `BlogPost.tsx` | Blog post library + editor split. Left: `PostLibrary(kind="blog")`. Right: `PostEditor(kind="blog")`. `handleLibraryLoad` auto-selects most recent post on mount and merges real headline data after creation. `NewPostDialog` for generating from a trend/search. |
| `LinkedInPost.tsx` | LinkedIn post library + editor split. Identical structure to BlogPost but `kind="linkedin"` and `showPublish=true`. |
| `InternalUpdates.tsx` | Tilicho workspace: mock internal thread list + discussion UI. `ComingSoonBadge` overlay at top-right. No backend wiring. |
| `SlackPost.tsx` | Tilicho workspace: mock ideation chat + Slack-style post preview. `ComingSoonBadge` overlay. No backend wiring. |
| `Insights.tsx` | **Route removed.** File still exists but `/insights` is no longer in the router. Can be deleted. |

## Last Session Changes
**Session date:** 2026-05-08

**Changes made:**
- `Trends.tsx` — replaced `let cancelled = false` pattern with `AbortController` in the per-trend stats fetch effect. When `dailyTrends` or `selectedDate` changes (e.g. user switches dates quickly), `ac.abort()` cancels all in-flight fetch calls immediately. Uses `if (!ac.signal.aborted) setTrendStats(...)` guard before state update. Added `.catch(() => {})` on the outer Promise.all to swallow abort errors cleanly.

**Reason:** Switching dates rapidly would fire 2N fetch requests (2 per trend) for the old date that couldn't be cancelled. With 20–30 trends, this means 40–60 concurrent requests that all completed even after the user moved to a different date. Now they're properly aborted.

**Outcome:** Fixed. In browser DevTools, switching dates while stats are loading now shows cancelled requests in the Network tab.

**Watch out for:** `Insights.tsx` still exists in this folder but is no longer in the router — delete it when doing cleanup. `handleLibraryLoad` in `BlogPost.tsx`/`LinkedInPost.tsx` uses a functional `setActive` updater — this is intentional to avoid stale closures; do not simplify to `setActive(p)`.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-08 | `Trends.tsx` | Added AbortController to per-trend stats fetch — date switching now cancels in-flight requests |
| 2026-05-01 | `BlogPost.tsx`, `LinkedInPost.tsx` | Full rewrite to PostLibrary+PostEditor split; handleLibraryLoad for auto-select; removed Insights route |
| 2026-05-01 | All files | Initial creation — wired Trends, Searches, BlogPost, LinkedInPost to backend; Tilicho pages mock + Coming Soon |
