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
  latest_run_state: string | null;
  pipeline_running: boolean;
  trend_count: number;
}

export type BackendStatus = 'ok' | 'unreachable' | 'no_run' | 'no_trends' | 'running';

export interface SearchResponse {
  run_id: string;
  run_date: string;
  topic: string;
  cached: boolean;
}

export type SearchState =
  | 'idle'
  | 'pending'
  | 'discovering'
  | 'scraping'
  | 'clustering'
  | 'summarizing'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed';

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
  role: 'user' | 'assistant';
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

export interface InsightListItem extends Insight {
  run_id: string;
  run_date: string;
  slug: string;
  context_kind: 'trend' | 'search';
  topic: string;
  headline: string;
}

export interface GeneratedPost {
  id: number;
  kind: 'linkedin' | 'blog';
  run_id: string;
  run_date: string;
  slug: string;
  content_markdown: string;
  tags: string[];
  status: 'draft' | 'edited' | 'published';
  linkedin_post_urn: string | null;
  created_at: string;
  updated_at: string;
}

export interface LinkedInStatus {
  connected: boolean;
  expires_at: string | null;
  member_urn: string | null;
  member_name: string | null;
}

export interface GeneratedPostWithHeadline extends GeneratedPost {
  headline: string;
}

export interface SlackMessage {
  user: string;
  text: string;
  ts: string;
}

export interface SlackHistory {
  channel: string;
  messages: SlackMessage[];
}

export interface SlackChatReply {
  reply: string;
}

export interface SlackGeneratedPost {
  kind: 'linkedin' | 'blog';
  content_markdown: string;
  tags: string[];
}

export interface SlackSendResult {
  ok: boolean;
  channel: string;
  ts: string;
}

export interface SlackLinkedInPublishResult {
  post_urn: string;
  status: string;
}
