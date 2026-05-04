# frontend/

## Purpose
Vite 6 + React 19 + React Router v7 SPA frontend for the LinkedIn Agent. Replaced the previous Next.js 16 App Router frontend this session. Serves the "Urban Mono" design system (B&W palette, sharp corners, Inter + JetBrains Mono, Material-3 surface tokens via Tailwind v4 `@theme`). Communicates with the Python FastAPI backend via an Express proxy layer (`server.ts`).

## Subfolders
| Folder | Role |
|---|---|
| `src/` | All React source code — pages, components, contexts, lib |
| `dist/` | Production build output (git-ignored) |
| `node_modules/` | npm dependencies (git-ignored) |

## Key Files
| File | Purpose |
|---|---|
| `server.ts` | Express server: 25+ proxy routes forwarding `/api/*` to FastAPI backend, plus Vite middleware in dev or static serving in prod. **Critical:** X-Forwarded-For injection on search/chat POSTs; 120s timeout on post generation; `/api/admin/linkedin/authorize` is a redirect, not a fetch. |
| `package.json` | npm deps and scripts (`dev`, `build`, `start`, `lint`). Key deps: react-markdown, rehype-sanitize, @tailwindcss/typography, tailwindcss-animate, motion, lucide-react, react-router-dom. |
| `vite.config.ts` | Vite + Tailwind v4 plugin + `@` alias → `src/` |
| `tsconfig.json` | Strict TS, `@/*` paths → `./src/*`, bundler module resolution |
| `index.html` | SPA shell — title "LinkedIn Agent", loads `/src/main.tsx` |
| `.env.example` | `BACKEND_URL=http://127.0.0.1:8000`, `PORT=3000` |

## Development
```bash
cd frontend
npm install
npm run dev      # http://localhost:3000 (Express + Vite middleware)
npm run build    # production build
npm start        # production (Express serves dist/)
npm run lint     # tsc --noEmit
```

## Architecture Notes
- **No Next.js features**: no App Router, no Route Handlers, no server components, no `next/font`. All API proxying is in `server.ts` (Express).
- **Tailwind v4** with CSS-first `@theme` config — no `tailwind.config.js`. Design tokens in `src/index.css`.
- **Sharp corners everywhere**: `* { @apply rounded-none!; }` in `index.css` — the Urban Mono signature. Never add `rounded-*` without checking this override.
- **`@/*` alias** points to `src/` — used in every import. Configured in both `tsconfig.json` and `vite.config.ts`.

## Last Session Changes
**Session date:** 2026-05-01

**Changes made:**
- **Entire frontend replaced**: migrated from Next.js 16 App Router → Vite 6 + React Router v7. Old frontend backed up to `frontend_old/`. New frontend sourced from `next-fe/` (AI Studio static prototype), fully wired to the backend.
- `server.ts` — expanded from 1 stub route to 25+ production proxy routes. Post generation timeouts raised to 120s.
- `src/` — full application: types, contexts, components, pages (see src/FOLDER.md).
- Multiple bug fixes across the session: `GET /posts/all` route ordering, `list_all_generated_posts` outerjoin replaced with two-step query, `onFirstLoad` callback for auto-selecting the most recent post on navigation return.

**Reason:** User requested migrating to the new Vite/Urban Mono frontend from `next-fe/` while preserving all backend wiring (chat, search, insights, post studio, LinkedIn OAuth).

**Outcome:** Full feature parity with old frontend. `tsc --noEmit` passes. LinkedIn and Blog Post pages correctly show all generated posts and auto-select the most recent on page load.

**Watch out for:** Backend must be restarted (`uvicorn backend.api.main:app --port 8000 --reload`) after any `routes_posts.py` changes for the new `/posts/all` endpoint to be active. The `frontend_old/` directory can be deleted once the new frontend is confirmed stable.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-01 | All files | Full migration from Next.js to Vite + Urban Mono; wired all backend features; Blog/LinkedIn post library + editor; auto-insight saving; post generation timeout fixes |
