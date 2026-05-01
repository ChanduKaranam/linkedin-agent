# frontend/app/api/

## Purpose
Next.js Route Handlers — a thin proxy layer that forwards browser requests to the Python FastAPI backend (`http://localhost:8000`). Each `route.ts` file exports HTTP method handlers (`GET`, `POST`, `PUT`).

## Subfolders / Route Tree
```
api/
├── health/                              GET      → backend /health
├── trends/
│   ├── today/                           GET      → backend /trends/today
│   ├── dates/                           GET      → backend /trends/dates
│   ├── by-date/[date]/                  GET      → backend /trends/by-date/{date}
│   └── [date]/[slug]/                   GET      → backend /trends/{date}/{slug}
├── search/
│   ├── route.ts                         POST     → backend /search
│   ├── history/                         GET      → backend /search/history
│   └── runs/[run_id]/
│       ├── route.ts                     GET      → backend /search/runs/{run_id}
│       └── trends/[slug]/               GET      → backend /search/runs/{run_id}/trends/{slug}
├── chat/
│   ├── [date]/[slug]/messages/          GET/POST → backend /chat/{date}/{slug}/messages
│   └── runs/[runId]/[slug]/messages/    GET/POST → backend /chat/runs/{runId}/{slug}/messages
├── insights/
│   ├── [date]/[slug]/                   GET/POST → backend /insights/{date}/{slug}
│   └── runs/[runId]/[slug]/             GET/POST → backend /insights/runs/{runId}/{slug}
├── posts/                               ← NEW (Post Studio)
│   ├── [postId]/route.ts                PATCH    → backend /posts/{postId}
│   ├── [postId]/publish/route.ts        POST     → backend /posts/{postId}/publish
│   ├── [date]/[slug]/route.ts           GET      → backend /posts/{date}/{slug}
│   ├── [date]/[slug]/linkedin/route.ts  POST     → backend /posts/{date}/{slug}/linkedin
│   ├── [date]/[slug]/blog/route.ts      POST     → backend /posts/{date}/{slug}/blog
│   └── runs/[runId]/[slug]/
│       ├── route.ts                     GET      → backend /posts/runs/{runId}/{slug}
│       ├── linkedin/route.ts            POST     → backend /posts/runs/{runId}/{slug}/linkedin
│       └── blog/route.ts               POST     → backend /posts/runs/{runId}/{slug}/blog
└── admin/
    ├── schedule/                        GET/PUT  → backend /admin/schedule
    └── linkedin/                        ← NEW
        ├── status/route.ts              GET      → backend /admin/linkedin/status
        └── authorize/route.ts           GET      → 302 → backend /admin/linkedin/authorize
```

## Last Session Changes
**Session date:** 2026-04-29

**Changes made:**
- Added 9 new route files under `posts/` (daily and run variants for list, generate-linkedin, generate-blog, patch, publish)
- Added 2 new route files under `admin/linkedin/` (status, authorize)

**Reason:** Post Studio feature — the browser communicates with the backend through these Next.js proxy routes (same pattern as all other routes in this folder).

**Outcome:** All new routes follow the existing pattern exactly: `const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"`, timeout via `AbortSignal.timeout()`, `NextResponse.json()` for errors. Timeouts are set to 60 s for generation endpoints (LLM calls can take 5–15 s) and 20 s for publish. The `authorize` route is a 302 redirect straight to the backend (which itself 302s to LinkedIn) — this two-hop redirect is intentional so the OAuth flow stays backend-controlled.

**Watch out for:** The `[postId]` and `[date]` dynamic segments could collide in Next.js routing if routes are not in the right folder depth. The current structure puts `[postId]/route.ts` (PATCH) and `[date]/[slug]/route.ts` (GET) at the same level — Next.js resolves these correctly because `[postId]` is a single-segment param while `[date]/[slug]` is two segments.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-04-29 | 11 new `route.ts` files under `posts/` and `admin/linkedin/` | Added Post Studio and LinkedIn OAuth proxy routes |
| — | — | Initial documentation created |
