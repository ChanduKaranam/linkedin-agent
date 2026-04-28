export interface Source {
  url: string;
  title: string;
  domain: string;
}

export interface TrendListItem {
  slug: string;
  headline: string;
  one_liner: string;
  source_count: number;
}

export interface TrendDetail {
  slug: string;
  run_date: string;
  headline: string;
  one_liner: string;
  detailed_markdown: string;
  key_points: string[];
  sources: Source[];
}

export interface Health {
  status: string;
  latest_run_date: string | null;
  trend_count: number;
}

export type BackendStatus = "ok" | "unreachable" | "no_run" | "no_trends";

export interface SearchResponse {
  run_id: string;
  run_date: string;
  topic: string;
  cached: boolean;
}

export type SearchState =
  | "idle"
  | "pending"
  | "discovering"
  | "scraping"
  | "clustering"
  | "summarizing"
  | "completed"
  | "completed_with_warnings"
  | "failed";

export interface SearchRunStatus {
  run_id: string;
  topic: string;
  state: SearchState;
  trend_count: number;
  last_error: string | null;
}

export interface ScheduleConfig {
  hour: number;
  minute: number;
  timezone: string;
}

export interface SearchHistoryItem {
  run_id: string;
  topic: string;
  run_date: string;
  state: string;
  trend_count: number;
  started_at: string;
}

export interface Citation {
  url: string;
  title: string;
  snippet: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  used_web: boolean;
  created_at: string;
}

export interface Insight {
  id: number;
  user_perspective: string;
  summary: string;
  tags: string[];
  created_at: string;
}
