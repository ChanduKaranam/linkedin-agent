# frontend/src/

## Purpose
All React source code for the LinkedIn Agent frontend. Organized into contexts (global state), components (reusable UI), pages (one per route), lib (utilities), and entry points.

## Subfolders
| Folder | Role |
|---|---|
| `components/` | Reusable React components — feature components + layout |
| `context/` | React Contexts for global state (backend status, search mode, workspace, time) |
| `pages/` | One component per route — Trends, Searches, BlogPost, LinkedInPost, InternalUpdates, SlackPost |
| `lib/` | `utils.ts` (`cn()` helper), `api.ts` (thin fetch wrappers) |

## Key Files
| File | Purpose |
|---|---|
| `main.tsx` | React 19 root — `createRoot().render(<App />)` |
| `App.tsx` | Provider stack + `<BrowserRouter>` + all `<Route>` definitions. Provider order: WorkspaceProvider → BackendStatusProvider → SearchModeProvider → TimeProvider → Router. `/insights` route removed. |
| `index.css` | Urban Mono design system: Google Fonts import, Tailwind v4 `@theme` tokens, `@layer base/components`. Plugins: `@tailwindcss/typography`, `tailwindcss-animate`. |
| `types.ts` | All shared TypeScript interfaces: `TrendListItem`, `TrendDetail`, `GeneratedPost`, `GeneratedPostWithHeadline`, `LinkedInStatus`, `ChatMessage`, `Insight`, `ScheduleConfig`, etc. |

## Last Session Changes
**Session date:** 2026-05-01

**Changes made:**
- `App.tsx` — removed `/insights` route (page removed from nav); added `BackendStatusProvider` and `SearchModeProvider` to the provider stack.
- `types.ts` — added `GeneratedPostWithHeadline extends GeneratedPost` with `headline: str` for the PostLibrary component.
- `index.css` — added `@plugin "@tailwindcss/typography"` and `@plugin "tailwindcss-animate"` directives.

**Reason:** Insights page removed per user request. New contexts needed for backend bootstrapping and search state sharing across Trends/Searches pages.

**Outcome:** All routes working. `tsc --noEmit` passes with zero errors.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-01 | `App.tsx`, `types.ts`, `index.css` | Removed /insights route; added BackendStatusContext and SearchModeContext providers; added GeneratedPostWithHeadline type; added typography/animate plugins |
| 2026-05-01 | All files | Initial creation — migrated from Next.js to Vite |
