# frontend/src/components/

## Purpose
Reusable React components. All are client-only (no server components — Vite SPA). Styled with Urban Mono Tailwind v4 utility classes. The `layout/` subfolder contains the Navbar and AppLayout.

## Subfolders
| Folder | Role |
|---|---|
| `layout/` | `Navbar.tsx` (workspace switcher, schedule editor, time modal, sub-nav) and `AppLayout.tsx` (page-transition wrapper) |

## Files
| File | Purpose |
|---|---|
| `ChatPanel.tsx` | Collapsible chat panel. Auto-saves every user message ≥30 chars as an insight for the topic (silently, fire-and-forget). Shows saved insights count in the header. Cites sources as pills. No manual "Save as insight" button — removed in favour of auto-save. |
| `PostEditor.tsx` | **New.** Standalone always-open post editor (no collapsible wrapper). Props: `post`, `kind`, `linkedinApiBase`, `blogApiBase`, `insightsApiBase` (optional), `onUpdated`, `showPublish`. Used directly by BlogPost/LinkedInPost pages. Handles: toolbar, regen instructions (120s timeout), photo upload, content editor/preview toggle, tags, LinkedIn publish. Does NOT auto-save edits as insights (backend PATCH already records edits as style samples). |
| `PostLibrary.tsx` | **New.** Left-rail scrollable list of all posts of a given kind. Fetches `GET /api/posts/all?kind=…`. Live search filter by headline/slug/tags. Groups by date bucket (Today/Yesterday/This Week/Older). Calls `onFirstLoad(firstPost)` on every fetch so pages can auto-select the most recent post. |
| `PostStudio.tsx` | Collapsible post studio for embedding inside TrendDetail/SearchResultView. Handles tab switching (linkedin/blog) and auto-fetch of existing posts for the current trend. Delegates editor UI to `PostEditor`. |
| `NewPostDialog.tsx` | **New.** Searchable source picker modal. Loads all daily trends (last 7 dates) + all completed search runs' trends into one unified searchable list. User picks a source, optionally types instructions, then clicks Generate. Routes to correct backend endpoint (daily vs search-run). 120s client timeout. |
| `TrendDetail.tsx` | Right-pane detail view for a daily trend. Embeds `ChatPanel` and `PostStudio`. |
| `TrendList.tsx` | Scrollable left-sidebar trend list. Active item: `border-l-primary`. |
| `DateSelector.tsx` | Horizontal date pill row. Active pill: `bg-primary text-on-primary`. |
| `SearchBar.tsx` | Search input with 2s polling for search pipeline state. Phase labels (Discovering/Scraping/etc.). Handles 429 rate-limit errors. Uses `react-router-dom` `useSearchParams`. |
| `SearchHistory.tsx` | Sidebar list of past search runs. `border-l-primary` for active. |
| `SearchResultView.tsx` | Right-pane view for search results. Embeds ChatPanel + PostStudio with run-scoped API bases. |
| `ScheduleEditor.tsx` | Schedule editor modal, embedded in Navbar for LinkedIn workspace. POST to `/api/admin/schedule`. |
| `EmptyState.tsx` | Three variants: `unreachable`, `no_run`, `no_trends`. Full-page centred layout. |
| `ComingSoonBadge.tsx` | Small "TILICHO · COMING SOON" pill for Tilicho-only pages. |

## Key Design Rules
- **No rounded corners** — `index.css` globally overrides with `rounded-none!`. Never add `rounded-*`.
- **`label-bold`** class for all uppercase tracking-widest section captions.
- **`btn-primary`** = black bg, white text, uppercase. **`btn-secondary`** = white bg, black border.
- **`card`** = white bg, `border-outline-variant`, `p-6`.
- **`input-field`** = surface-container-low bg, outline-variant border, focus border-primary.

## Last Session Changes
**Session date:** 2026-05-01

**Changes made:**
- `ChatPanel.tsx` — auto-saves insights silently (≥30 char threshold to filter trivial replies). Removed manual "+ Save as insight" UI.
- `PostEditor.tsx` — created new component. Removed the post-edit auto-save insight call (backend PATCH already records edits as style samples via `add_style_sample`). Added 120s `AbortSignal.timeout` on generation fetch.
- `PostLibrary.tsx` — created new component. Fixed `onFirstLoad` to fire on every list fetch (not once) so returning to the page auto-selects the most recent post. Improved error handling (`throw` on non-OK instead of returning `[]` silently).
- `PostStudio.tsx` — refactored to delegate editor UI to `PostEditor`. Now thinner: just the collapsible header + tab bar + initial-generate empty state.
- `NewPostDialog.tsx` — full rewrite. Replaced separate dropdown pickers with a single searchable unified list of all available sources (daily trends + search run trends). Auto-focuses search input. Shows a "selected source" black bar at top when item is chosen.
- `layout/Navbar.tsx` — removed "My Insights" nav item. Keeps ScheduleEditor (LinkedIn workspace only), workspace switcher, time modal.

**Reason:** Multiple UX fixes: posts disappearing on navigation, insight auto-save polluting the context with post drafts, dialog being hard to use with many trends, library not showing posts.

**Outcome:** All components type-check clean. Library shows posts correctly. Navigation no longer loses the selected post.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-01 | `ChatPanel.tsx`, `PostEditor.tsx` (new), `PostLibrary.tsx` (new), `PostStudio.tsx`, `NewPostDialog.tsx` (new), `layout/Navbar.tsx` | Auto-save insight fix; PostEditor extracted; PostLibrary onFirstLoad fix; NewPostDialog unified searchable picker; removed Insights nav |
| 2026-05-01 | All files | Initial creation — migrated and restyled from Next.js frontend components |
