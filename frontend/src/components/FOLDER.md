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
| `PostEditor.tsx` | Standalone always-open post editor. Props: `post`, `kind`, `linkedinApiBase`, `blogApiBase`, `insightsApiBase` (optional), `onUpdated`, `showPublish`. Handles: toolbar, regen instructions (120s timeout), photo upload, content editor/preview toggle, tags, LinkedIn publish. Does NOT auto-save edits as insights. **Bug fix (2026-05-06):** `photoUrl` + `photoDataUrl` are both cleared on `post.id` change — previously only `photoDataUrl` was cleared, leaving the thumbnail visible but data gone, so publish silently sent no image. |
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
**Session date:** 2026-05-06

**Changes made:**
- `PostEditor.tsx` — in the `useEffect([post.id])` reset block, added `setPhotoUrl(prev => { if (prev) URL.revokeObjectURL(prev); return null; })` alongside the existing `setPhotoDataUrl(null)`. Previously only `photoDataUrl` was cleared; `photoUrl` (the blob URL driving the thumbnail `<img>`) was left set. When a user added a photo then triggered a post-id change (e.g. regenerated the post), the thumbnail remained visible but `photoDataUrl` was null — clicking Publish sent no image to LinkedIn.

**Reason:** User reported images added before publish weren't showing up on LinkedIn. The thumbnail preview gave false confidence the image was still attached.

**Outcome:** Fix is in place. Uses functional `setPhotoUrl` updater to safely revoke the old blob URL inside the effect without needing `photoUrl` as a dependency.

**Watch out for:** If `post.id` changes immediately after a user selects a photo (e.g. they click Regenerate right after adding an image), the photo will be cleared. This is intentional — the new generated post is a different document. The user must re-select the photo for the new post.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-06 | `PostEditor.tsx` | Fixed photoUrl not cleared on post.id change — thumbnail stayed visible but data was null, causing publish to silently send no image |
| 2026-05-01 | `ChatPanel.tsx`, `PostEditor.tsx` (new), `PostLibrary.tsx` (new), `PostStudio.tsx`, `NewPostDialog.tsx` (new), `layout/Navbar.tsx` | Auto-save insight fix; PostEditor extracted; PostLibrary onFirstLoad fix; NewPostDialog unified searchable picker; removed Insights nav |
| 2026-05-01 | All files | Initial creation — migrated and restyled from Next.js frontend components |
