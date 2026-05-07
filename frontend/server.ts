import 'dotenv/config';
import express, { Request, Response } from 'express';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BACKEND = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000';
const PORT = Number(process.env.PORT ?? 3000);

// ---------------------------------------------------------------------------
// Proxy helper
// ---------------------------------------------------------------------------
interface ProxyOpts {
  method?: string;
  backendPath: string;
  timeoutMs: number;
  forwardIp?: boolean;
  req: Request;
  res: Response;
}

async function proxy({ method, backendPath, timeoutMs, forwardIp, req, res }: ProxyOpts) {
  const url = `${BACKEND}${backendPath}`;
  const m = (method ?? req.method).toUpperCase();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };

  if (forwardIp) {
    const fwd = req.headers['x-forwarded-for'];
    const ip =
      (Array.isArray(fwd) ? fwd[0] : fwd?.split(',')[0]?.trim()) ??
      req.headers['x-real-ip'] as string ??
      req.socket.remoteAddress ??
      'browser';
    headers['X-Forwarded-For'] = ip;
  }

  try {
    const body = ['POST', 'PUT', 'PATCH'].includes(m) && req.body
      ? JSON.stringify(req.body)
      : undefined;

    const response = await fetch(url, {
      method: m,
      headers,
      body,
      signal: AbortSignal.timeout(timeoutMs),
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      let payload: unknown;
      try { payload = JSON.parse(text); } catch { payload = { error: 'upstream_error', detail: text }; }
      res.status(response.status === 404 ? 404 : response.status).json(payload);
      return;
    }

    const data = await response.json().catch(() => null);
    res.json(data);
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'TimeoutError') {
      res.status(504).json({ error: 'gateway_timeout' });
    } else {
      res.status(503).json({ error: 'backend_unreachable' });
    }
  }
}

async function sseProxy({ backendPath, req, res }: { backendPath: string; req: Request; res: Response }) {
  const url = `${BACKEND}${backendPath}`;
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body),
      signal: AbortSignal.timeout(120_000),
    });
    if (!response.ok || !response.body) {
      res.write(`data: ${JSON.stringify({ type: 'error', detail: 'Backend error' })}\n\n`);
      res.write('data: [DONE]\n\n');
      res.end();
      return;
    }
    const reader = response.body.getReader();
    req.on('close', () => { reader.cancel().catch(() => {}); });
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      res.write(value);
    }
    res.end();
  } catch (err: unknown) {
    if (!res.headersSent) {
      res.write(`data: ${JSON.stringify({ type: 'error', detail: 'Backend unreachable' })}\n\n`);
      res.write('data: [DONE]\n\n');
    }
    res.end();
  }
}

async function startServer() {
  const app = express();
  app.use(express.json({ limit: '25mb' }));

  // -------------------------------------------------------------------------
  // Health
  // -------------------------------------------------------------------------
  app.get('/api/health', (req, res) => proxy({ backendPath: '/health', timeoutMs: 5_000, req, res }));

  // -------------------------------------------------------------------------
  // Trends
  // -------------------------------------------------------------------------
  app.get('/api/trends/today', (req, res) => proxy({ backendPath: '/trends/today', timeoutMs: 10_000, req, res }));
  app.get('/api/trends/dates', (req, res) => proxy({ backendPath: '/trends/dates', timeoutMs: 5_000, req, res }));
  app.get('/api/trends/by-date/:date', (req, res) =>
    proxy({ backendPath: `/trends/by-date/${req.params.date}`, timeoutMs: 10_000, req, res }));
  app.get('/api/trends/:date/:slug', (req, res) =>
    proxy({ backendPath: `/trends/${req.params.date}/${req.params.slug}`, timeoutMs: 10_000, req, res }));

  // -------------------------------------------------------------------------
  // Search
  // -------------------------------------------------------------------------
  app.post('/api/search', (req, res) =>
    proxy({ backendPath: '/search', timeoutMs: 15_000, forwardIp: true, req, res }));
  app.get('/api/search/history', (req, res) =>
    proxy({ backendPath: '/search/history', timeoutMs: 8_000, req, res }));
  app.get('/api/search/runs/:run_id', (req, res) =>
    proxy({ backendPath: `/search/runs/${req.params.run_id}`, timeoutMs: 10_000, req, res }));
  app.get('/api/search/runs/:run_id/trends', (req, res) =>
    proxy({ backendPath: `/search/runs/${req.params.run_id}/trends`, timeoutMs: 10_000, req, res }));
  app.get('/api/search/runs/:run_id/trends/:slug', (req, res) =>
    proxy({ backendPath: `/search/runs/${req.params.run_id}/trends/${req.params.slug}`, timeoutMs: 10_000, req, res }));

  // -------------------------------------------------------------------------
  // Chat — dual namespace (date/slug and runs/runId/slug)
  // -------------------------------------------------------------------------
  app.get('/api/chat/:date/:slug/messages', (req, res) =>
    proxy({ backendPath: `/chat/${req.params.date}/${req.params.slug}/messages`, timeoutMs: 10_000, req, res }));
  app.delete('/api/chat/:date/:slug/messages', (req, res) =>
    proxy({ method: 'DELETE', backendPath: `/chat/${req.params.date}/${req.params.slug}/messages`, timeoutMs: 10_000, req, res }));
  app.post('/api/chat/:date/:slug/messages', (req, res) =>
    proxy({ backendPath: `/chat/${req.params.date}/${req.params.slug}/messages`, timeoutMs: 120_000, forwardIp: true, req, res }));
  app.post('/api/chat/:date/:slug/messages/stream', (req, res) =>
    sseProxy({ backendPath: `/chat/${req.params.date}/${req.params.slug}/messages/stream`, req, res }));
  app.get('/api/chat/runs/:runId/:slug/messages', (req, res) =>
    proxy({ backendPath: `/chat/runs/${req.params.runId}/${req.params.slug}/messages`, timeoutMs: 10_000, req, res }));
  app.delete('/api/chat/runs/:runId/:slug/messages', (req, res) =>
    proxy({ method: 'DELETE', backendPath: `/chat/runs/${req.params.runId}/${req.params.slug}/messages`, timeoutMs: 10_000, req, res }));
  app.post('/api/chat/runs/:runId/:slug/messages', (req, res) =>
    proxy({ backendPath: `/chat/runs/${req.params.runId}/${req.params.slug}/messages`, timeoutMs: 120_000, forwardIp: true, req, res }));
  app.post('/api/chat/runs/:runId/:slug/messages/stream', (req, res) =>
    sseProxy({ backendPath: `/chat/runs/${req.params.runId}/${req.params.slug}/messages/stream`, req, res }));

  // -------------------------------------------------------------------------
  // Insights — dual namespace
  // -------------------------------------------------------------------------
  app.get('/api/insights/:date/:slug', (req, res) =>
    proxy({ backendPath: `/insights/${req.params.date}/${req.params.slug}`, timeoutMs: 10_000, req, res }));
  app.get('/api/insights/all', (req, res) =>
    proxy({ backendPath: '/insights/all', timeoutMs: 10_000, req, res }));
  app.post('/api/insights/:date/:slug', (req, res) =>
    proxy({ backendPath: `/insights/${req.params.date}/${req.params.slug}`, timeoutMs: 15_000, req, res }));
  app.get('/api/insights/runs/:runId/:slug', (req, res) =>
    proxy({ backendPath: `/insights/runs/${req.params.runId}/${req.params.slug}`, timeoutMs: 10_000, req, res }));
  app.post('/api/insights/runs/:runId/:slug', (req, res) =>
    proxy({ backendPath: `/insights/runs/${req.params.runId}/${req.params.slug}`, timeoutMs: 15_000, req, res }));

  // -------------------------------------------------------------------------
  // Posts — dual namespace + by-id actions
  // -------------------------------------------------------------------------
  // List all posts of a given kind (for the library view)
  app.get('/api/posts/all', (req, res) => {
    const qs = new URLSearchParams(req.query as Record<string, string>).toString();
    return proxy({ backendPath: `/posts/all?${qs}`, timeoutMs: 10_000, req, res });
  });

  app.get('/api/posts/:date/:slug', (req, res) =>
    proxy({ backendPath: `/posts/${req.params.date}/${req.params.slug}`, timeoutMs: 10_000, req, res }));
  app.post('/api/posts/:date/:slug/linkedin', (req, res) =>
    proxy({ backendPath: `/posts/${req.params.date}/${req.params.slug}/linkedin`, timeoutMs: 120_000, req, res }));
  app.post('/api/posts/:date/:slug/blog', (req, res) =>
    proxy({ backendPath: `/posts/${req.params.date}/${req.params.slug}/blog`, timeoutMs: 120_000, req, res }));
  app.get('/api/posts/runs/:runId/:slug', (req, res) =>
    proxy({ backendPath: `/posts/runs/${req.params.runId}/${req.params.slug}`, timeoutMs: 10_000, req, res }));
  app.post('/api/posts/runs/:runId/:slug/linkedin', (req, res) =>
    proxy({ backendPath: `/posts/runs/${req.params.runId}/${req.params.slug}/linkedin`, timeoutMs: 120_000, req, res }));
  app.post('/api/posts/runs/:runId/:slug/blog', (req, res) =>
    proxy({ backendPath: `/posts/runs/${req.params.runId}/${req.params.slug}/blog`, timeoutMs: 120_000, req, res }));
  app.get('/api/posts/by-id/:postId', (req, res) =>
    proxy({ backendPath: `/posts/by-id/${req.params.postId}`, timeoutMs: 10_000, req, res }));
  app.delete('/api/posts/by-id/:postId', (req, res) =>
    proxy({ method: 'DELETE', backendPath: `/posts/${req.params.postId}`, timeoutMs: 15_000, req, res }));
  app.patch('/api/posts/by-id/:postId', (req, res) =>
    proxy({ method: 'PATCH', backendPath: `/posts/${req.params.postId}`, timeoutMs: 15_000, req, res }));
  app.post('/api/posts/by-id/:postId/publish', (req, res) =>
    proxy({ backendPath: `/posts/${req.params.postId}/publish`, timeoutMs: 90_000, req, res }));

  // -------------------------------------------------------------------------
  // Slack
  // -------------------------------------------------------------------------
  app.get('/api/slack/channels/:channelId/messages', (req, res) => {
    const qs = new URLSearchParams(req.query as Record<string, string>).toString();
    const suffix = qs ? `?${qs}` : '';
    return proxy({
      backendPath: `/slack/channels/${req.params.channelId}/messages${suffix}`,
      timeoutMs: 20_000,
      req,
      res,
    });
  });
  app.post('/api/slack/chat', (req, res) =>
    proxy({ backendPath: '/slack/chat', timeoutMs: 120_000, req, res }));
  app.post('/api/slack/generate/linkedin', (req, res) =>
    proxy({ backendPath: '/slack/generate/linkedin', timeoutMs: 120_000, req, res }));
  app.post('/api/slack/generate/blog', (req, res) =>
    proxy({ backendPath: '/slack/generate/blog', timeoutMs: 120_000, req, res }));
  app.post('/api/slack/post', (req, res) =>
    proxy({ backendPath: '/slack/post', timeoutMs: 30_000, req, res }));
  app.post('/api/slack/publish/linkedin', (req, res) =>
    proxy({ backendPath: '/slack/publish/linkedin', timeoutMs: 30_000, req, res }));

  // -------------------------------------------------------------------------
  // Admin
  // -------------------------------------------------------------------------
  // GET reads the public schedule endpoint; POST writes to the debug-gated one.
  app.get('/api/admin/schedule', (req, res) =>
    proxy({ method: 'GET', backendPath: '/schedule', timeoutMs: 5_000, req, res }));
  app.post('/api/admin/schedule', (req, res) =>
    proxy({ method: 'POST', backendPath: '/admin/schedule', timeoutMs: 5_000, req, res }));

  app.get('/api/admin/linkedin/status', (req, res) =>
    proxy({ backendPath: '/admin/linkedin/status', timeoutMs: 10_000, req, res }));

  // LinkedIn authorize — must redirect, not fetch
  app.get('/api/admin/linkedin/authorize', (_req, res) => {
    res.redirect(`${BACKEND}/admin/linkedin/authorize`);
  });

  // -------------------------------------------------------------------------
  // Vite SPA
  // -------------------------------------------------------------------------
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running at http://localhost:${PORT}`);
  });
}

startServer();
