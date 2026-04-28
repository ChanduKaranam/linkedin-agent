import { NextResponse } from "next/server";
import type { TrendListItem } from "@/types";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ date: string }> }
) {
  const { date } = await params;
  try {
    const res = await fetch(`${BACKEND}/trends/by-date/${date}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) return NextResponse.json([], { status: res.status });
    const data: TrendListItem[] = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json([]);
  }
}
