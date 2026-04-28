import { NextResponse } from "next/server";
import type { TrendDetail } from "@/types";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ date: string; slug: string }> }
) {
  const { date, slug } = await params;
  try {
    const res = await fetch(`${BACKEND}/trends/${date}/${slug}`, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(10_000),
    });
    if (res.status === 404) return NextResponse.json({ error: "not_found" }, { status: 404 });
    if (!res.ok) return NextResponse.json({ error: "upstream_error" }, { status: res.status });
    const data: TrendDetail = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "backend_unreachable" }, { status: 503 });
  }
}
