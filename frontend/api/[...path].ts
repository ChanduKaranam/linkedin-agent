const PASS_THROUGH_REQUEST_HEADERS = ["content-type", "cookie", "x-forwarded-for", "x-real-ip"];
const PASS_THROUGH_RESPONSE_HEADERS = ["content-type", "set-cookie"];

function normalizeBackendUrl(raw: string): string {
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}

function readPathParam(path: string | string[] | undefined): string {
  if (!path) return "";
  return Array.isArray(path) ? path.join("/") : path;
}

export default async function handler(req: any, res: any) {
  const backendRaw = process.env.BACKEND_URL;
  if (!backendRaw) {
    res.status(500).json({ error: "missing_backend_url" });
    return;
  }

  const backend = normalizeBackendUrl(backendRaw);
  const path = readPathParam(req.query.path);

  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(req.query)) {
    if (key === "path") continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== null && item !== undefined) query.append(key, String(item));
      }
    } else if (value !== undefined && value !== null) {
      query.append(key, String(value));
    }
  }

  const target = `${backend}/${path}${query.toString() ? `?${query.toString()}` : ""}`;

  const headers = new Headers();
  for (const name of PASS_THROUGH_REQUEST_HEADERS) {
    const value = req.headers[name];
    if (!value) continue;
    if (Array.isArray(value)) headers.set(name, value.join(", "));
    else headers.set(name, value);
  }

  const method = (req.method ?? "GET").toUpperCase();
  const hasBody = !["GET", "HEAD"].includes(method);
  const body = hasBody && req.body ? JSON.stringify(req.body) : undefined;

  try {
    const upstream = await fetch(target, {
      method,
      headers,
      body,
    });

    for (const name of PASS_THROUGH_RESPONSE_HEADERS) {
      const value = upstream.headers.get(name);
      if (value) res.setHeader(name, value);
    }

    const text = await upstream.text();
    res.status(upstream.status);
    try {
      res.send(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch {
    res.status(503).json({ error: "backend_unreachable" });
  }
}

