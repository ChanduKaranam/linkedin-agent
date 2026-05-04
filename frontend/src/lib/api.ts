export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  opts?: { timeoutMs?: number }
): Promise<T> {
  const signal = opts?.timeoutMs ? AbortSignal.timeout(opts.timeoutMs) : undefined;
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as Record<string, unknown>;
    throw Object.assign(new Error(String(err.detail ?? err.error ?? res.status)), { status: res.status, data: err });
  }
  return res.json() as Promise<T>;
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as Record<string, unknown>;
    throw Object.assign(new Error(String(err.detail ?? err.error ?? res.status)), { status: res.status, data: err });
  }
  return res.json() as Promise<T>;
}
