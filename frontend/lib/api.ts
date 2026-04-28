import type { Health, TrendDetail, TrendListItem } from "@/types";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
const TIMEOUT = 10_000;

async function fetchJSON<T>(path: string): Promise<T> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), TIMEOUT);
  try {
    const res = await fetch(`${BACKEND}${path}`, {
      signal: controller.signal,
      next: { revalidate: 3600 },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(id);
  }
}

export async function fetchHealth(): Promise<Health> {
  return fetchJSON<Health>("/health");
}

export async function fetchTrendsToday(): Promise<TrendListItem[]> {
  return fetchJSON<TrendListItem[]>("/trends/today");
}

export async function fetchTrendDetail(date: string, slug: string): Promise<TrendDetail> {
  return fetchJSON<TrendDetail>(`/trends/${date}/${slug}`);
}
