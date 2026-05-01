import { NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ date: string; slug: string }> }
) {
  const { date, slug } = await params;
  try {
    const res = await fetch(`${BACKEND}/posts/${date}/${slug}`, {
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) return NextResponse.json({ error: "upstream_error" }, { status: res.status });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "backend_unreachable" }, { status: 503 });
  }
}
