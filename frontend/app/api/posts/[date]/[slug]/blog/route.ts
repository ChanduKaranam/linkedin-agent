import { NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ date: string; slug: string }> }
) {
  const { date, slug } = await params;
  try {
    const res = await fetch(`${BACKEND}/posts/${date}/${slug}/blog`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(60_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "backend_unreachable" }, { status: 503 });
  }
}
