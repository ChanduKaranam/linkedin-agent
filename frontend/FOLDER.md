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
| `server.ts` | Express server: 25+ proxy routes forwarding `/api/*` to FastAPI backend, plus Vite middleware in dev or static serving in prod. **Critical:** X-Forwarded-For injection on search/chat POSTs; 120s timeout on post generation; `/api/admin/linkedin/authorize` is a redirect, not a fetch. Body limit is 10mb. SSE proxy forwards Cookie header (auth required). `http.createServer` with `keepAliveTimeout=65s`. Global error handler + `unhandledRejection` handler. |
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
**Session date:** 2026-05-08

**Changes made:**
- `server.ts` — (1) SSE proxy (`sseProxy`) now forwards the `Cookie` header to the backend. This was a silent auth bug: all streaming chat requests were unauthenticated because the SSE proxy didn't pass cookies, unlike the regular `proxy()` function. (2) Body limit reduced from 25mb → 10mb (covers base64 images up to ~7.5MB; 25mb was excessive and a DoS amplifier). (3) Replaced bare `app.listen()` with `http.createServer(app)` + `server.keepAliveTimeout=65s`, `server.headersTimeout=70s` to prevent 502s from reverse proxies that timeout idle connections. (4) Added global Express error handler `(err, req, res, next)`. (5) Added `process.on('unhandledRejection')` handler. (6) Changed `startServer()` to `void startServer()` (was bare call, rejection would be silent). (7) Added proxy route for `GET /api/admin/logs` (new backend endpoint from Phase 0).

**Reason:** Several reliability and security fixes: SSE cookie omission meant chat streaming silently failed auth (users might not have noticed if the backend happened to not enforce auth in some paths); the 25mb body limit was a security concern; missing error handlers meant crashes were silent in production; keepAlive timeouts are needed when behind nginx/Vercel.

**Outcome:** All changes working. TypeScript (`tsc --noEmit`) passes. Frontend server must be restarted to apply.

**Watch out for:** The body limit reduction (25mb → 10mb) could break LinkedIn image upload if users try to upload images > ~7.5MB. LinkedIn's own limit is 8MB, so typical images are fine. If this becomes an issue, raise to 12mb. The SSE proxy now correctly requires the user to be authenticated for chat streaming — this was always the intended behavior.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-08 | `server.ts` | Fixed SSE cookie forwarding (auth bug); reduced body limit to 10mb; added keepAlive timeouts + error handlers; added /api/admin/logs route |
| 2026-05-06 | `server.ts` | Raised Express JSON body limit to 25mb and publish timeout to 90s to fix LinkedIn image upload being dropped |
| 2026-05-01 | All files | Full migration from Next.js to Vite + Urban Mono; wired all backend features; Blog/LinkedIn post library + editor; auto-insight saving; post generation timeout fixes |
