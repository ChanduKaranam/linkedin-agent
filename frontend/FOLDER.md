# frontend/

## Purpose
Next.js 14 TypeScript frontend for the AI Trend Agent. Renders a two-panel digest UI: a left sidebar listing trends or search history, and a right panel showing trend details with a chat interface. Communicates with the Python backend via the Next.js API routes (proxy layer).

## Subfolders
| Folder | Role |
|---|---|
| `app/` | Next.js App Router — pages, layouts, and API route handlers |
| `components/` | Reusable React client components |
| `lib/` | Shared utilities (API client) |
| `public/` | Static assets served at `/` |

## Key Files
| File | Purpose |
|---|---|
| `package.json` | Node dependencies and scripts (`dev`, `build`, `start`, `lint`) |
| `next.config.ts` | Next.js configuration (rewrites, image domains, etc.) |
| `tsconfig.json` | TypeScript compiler options |
| `postcss.config.mjs` | PostCSS / Tailwind CSS pipeline |
| `types.ts` | Shared TypeScript interfaces — includes `GeneratedPost` and `LinkedInStatus` as of 2026-04-29 |
| `.env.local` | Local env overrides — `BACKEND_URL` etc. Never committed. |
| `AGENTS.md` / `CLAUDE.md` | Agent instructions: warns that this Next.js version has breaking API changes from training data |

## Development
```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
npm run build    # production build
```

## Last Session Changes
**Session date:** 2026-04-29

**Changes made:**
- `types.ts` — added `GeneratedPost` and `LinkedInStatus` interfaces

**Reason:** Post Studio feature — the frontend needs typed representations of generated post drafts and the LinkedIn connection state.

**Outcome:** `tsc --noEmit` passes with zero errors after all Post Studio changes.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-04-29 | `types.ts` | Added GeneratedPost and LinkedInStatus TypeScript interfaces |
| — | — | Initial documentation created |
