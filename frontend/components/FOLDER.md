# frontend/components/

## Purpose
Reusable React client components. All are `"use client"` unless noted. Styled with Tailwind CSS utility classes.

## Files
| File | Purpose |
|---|---|
| `SearchBar.tsx` | Top-centre search input. On submit: calls `POST /api/search`, polls until run completes. |
| `TrendList.tsx` | Scrollable left-sidebar list of `TrendListItem[]`. |
| `TrendDetail.tsx` | Right-panel detail view for a daily trend. Embeds `ChatPanel` and `PostStudio`. |
| `ChatPanel.tsx` | Collapsible chat + insights UI. Sends messages, displays citations, saves insights. |
| `PostStudio.tsx` | **New.** Collapsible Post Studio panel. LinkedIn / Blog tabs. Generate → edit → save edits → publish (LinkedIn) or copy/download (blog). Loads existing drafts on open; polls `/api/admin/linkedin/status` for connection state. |
| `DateSelector.tsx` | Horizontal scrollable date-pill row. |
| `ScheduleEditor.tsx` | Clock icon button in header. Opens popover to edit pipeline schedule. |
| `SearchResultView.tsx` | Right-panel view for ad-hoc search results. Now accepts `postsApiBase`, `linkedinApiBase`, `blogApiBase` props and embeds `PostStudio`. |
| `SearchHistory.tsx` | "Searches" sidebar tab — lists past search runs. |
| `EmptyState.tsx` | Full-page placeholder for backend-unreachable or no-run states. |
| `TrendTabs.tsx` | Tab bar within trend detail (Summary / Key Points / Sources). |

## Last Session Changes
**Session date:** 2026-05-01

**Changes made:**
- `PostStudio.tsx` — major enhancements: (1) **LinkedIn preview card** — a `LinkedInPreviewCard` sub-component renders a pixel-accurate LinkedIn post mockup (avatar, post text, hashtags in LinkedIn blue, photo, engagement bar). (2) **Unified Preview/Edit toggle** — replaces the blog-only Preview button; works for both tabs. (3) **Photo upload** — "Add photo" button (dashed border) lets the user attach an image; shown as a thumbnail inline; displayed in both LinkedIn card and blog (as header image) previews. Object URL is cleaned up on unmount/change. (4) **Regeneration instructions input** — an auto-growing textarea + Regenerate button row replaces the old standalone Regenerate button. The user types optional freeform change requests; ⌘Enter / Ctrl+Enter also triggers regeneration. Instructions are sent as `user_instructions` in the POST body and cleared after success.

**Reason:** Better UX for post editing — user needs to see what the LinkedIn post will look like before publishing, attach a photo to the post, and iterate with specific change requests instead of regenerating blindly.

**Outcome:** Zero TypeScript errors (`tsc --noEmit` passed). Photo upload is frontend-only (object URL, no backend storage); the LinkedIn publish endpoint does not yet attach the photo to the LinkedIn API call — that would require backend image upload support.

**Watch out for:** The `photoUrl` is a local `URL.createObjectURL` blob and is revoked on unmount. It is never sent to the backend. If you add LinkedIn image publishing later, you'll need to upload the file to the backend as multipart/form-data and pass the asset URN to the LinkedIn API separately.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-01 | `PostStudio.tsx` | Added LinkedIn preview card, photo upload, unified preview toggle, and regeneration instructions input |
| 2026-04-29 | `PostStudio.tsx` (new), `TrendDetail.tsx`, `SearchResultView.tsx` | Added Post Studio component; wired into both daily and search-run detail views |
| — | — | Initial documentation created |
