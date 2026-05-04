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
**Session date:** 2026-05-01

**Changes made:**
- `BlogPost.tsx` — full rewrite. Now uses PostLibrary + PostEditor layout. `handleLibraryLoad` callback merges real post data from library into `active` state. `handleCreated` sets active immediately with slug-derived headline for instant feedback, then `handleLibraryLoad` updates with real data on list refresh.
- `LinkedInPost.tsx` — full rewrite. Same pattern as BlogPost. `showPublish=true` passed to PostEditor to show LinkedIn connect/publish section.
- `Insights.tsx` — removed from router (`App.tsx`) and navbar (`Navbar.tsx`). File retained but unused.

**Reason:** BlogPost and LinkedInPost were showing "0 posts" on navigation return because: (1) the `list_all_generated_posts` outerjoin was broken, (2) `onFirstLoad` only fired once. Both fixed at the component and backend level.

**Outcome:** Posts persist across navigation. Library auto-selects most recent post on every page visit.

**Watch out for:** `Insights.tsx` still exists — delete it when cleaning up. `handleLibraryLoad` uses functional `setActive` updater (not a direct `setActive(p)`) — this is intentional to avoid stale closure bugs. Do not simplify it to `setActive(p)` or it will overwrite user selections.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-01 | `BlogPost.tsx`, `LinkedInPost.tsx` | Full rewrite to PostLibrary+PostEditor split; handleLibraryLoad for auto-select; removed Insights route |
| 2026-05-01 | All files | Initial creation — wired Trends, Searches, BlogPost, LinkedInPost to backend; Tilicho pages mock + Coming Soon |
