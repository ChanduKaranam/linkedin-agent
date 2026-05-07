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
| `server.ts` | Express server: 25+ proxy routes forwarding `/api/*` to FastAPI backend, plus Vite middleware in dev or static serving in prod. **Critical:** X-Forwarded-For injection on search/chat POSTs; 120s timeout on post generation; `/api/admin/linkedin/authorize` is a redirect, not a fetch. Body limit is 25mb (required for image uploads). Publish endpoint timeout is 90s (image upload + post creation can take up to 60s). |
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
**Session date:** 2026-05-06

**Changes made:**
- `server.ts` — raised Express JSON body limit from default 100kb to `25mb`. Previously any image larger than ~75KB (base64 overhead: 1.33×) was silently rejected by Express before reaching the proxy handler, causing LinkedIn publish to go through without the image.
- `server.ts` — raised publish endpoint proxy timeout from 20s to 90s. LinkedIn image upload involves two round trips (initializeUpload + PUT bytes) plus the post creation call; backend can take up to 60s for large images, so 20s was reliably too short.

**Reason:** Users uploading images for LinkedIn posts saw the post publish successfully but without the attached image. Root cause was a two-part bug: (1) Express body size limit rejecting large images; (2) a stale-state bug in `PostEditor.tsx` where `photoDataUrl` was cleared on post change but the thumbnail preview (`photoUrl`) was not, so users saw the image preview but the data was gone.

**Outcome:** Both bugs fixed. Frontend server must be restarted to pick up `server.ts` changes.

**Watch out for:** Express's `express.json({ limit: '25mb' })` only controls JSON body parsing. If file upload is ever changed to `multipart/form-data`, a separate `multer` or similar limit applies. The 90s proxy timeout must stay above the backend's combined `httpx` timeouts (40s upload + 20s post = 60s max).

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-06 | `server.ts` | Raised Express JSON body limit to 25mb and publish timeout to 90s to fix LinkedIn image upload being dropped |
| 2026-05-01 | All files | Full migration from Next.js to Vite + Urban Mono; wired all backend features; Blog/LinkedIn post library + editor; auto-insight saving; post generation timeout fixes |
