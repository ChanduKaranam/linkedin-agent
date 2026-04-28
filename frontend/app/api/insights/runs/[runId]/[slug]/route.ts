import { NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ runId: string; slug: string }> }
) {
  const { runId, slug } = await params;
  try {
    const res = await fetch(`${BACKEND}/insights/runs/${runId}/${slug}`, {
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) return NextResponse.json({ error: "upstream_error" }, { status: res.status });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "backend_unreachable" }, { status: 503 });
  }
}

export async function POST(
  req: Request,
  { params }: { params: Promise<{ runId: string; slug: string }> }
) {
  const { runId, slug } = await params;
  const body = await req.json().catch(() => ({}));
  try {
    const res = await fetch(`${BACKEND}/insights/runs/${runId}/${slug}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "backend_unreachable" }, { status: 503 });
  }
}
