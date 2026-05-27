from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl


class Source(BaseModel):
    url: str
    title: str
    domain: str


class DiscoveredUrl(BaseModel):
    url: str
    title: str
    snippet: str = ""
    source_query: str = ""


class ScrapedPage(BaseModel):
    url: str
    title: str
    markdown: str
    domain: str
    scrape_method: str = "crawl4ai"


class Cluster(BaseModel):
    trend_id: str
    member_indices: list[int]


class TrendSummary(BaseModel):
    headline: str = Field(max_length=120)
    one_liner: str = Field(max_length=240)
    detailed_markdown: str
    key_points: Annotated[list[str], Field(min_length=2, max_length=8)]


class DailyBriefs(BaseModel):
    """Output schema for the daily synthesis LLM call — list of distinct story briefs.

    Hard cap: 5–15 unique headlines. The LLM is instructed to merge minor stories,
    so the schema rejects anything above 15 at validation time.
    """
    trends: Annotated[list[TrendSummary], Field(min_length=1, max_length=15)]


class PersistedTrend(BaseModel):
    id: int | None = None
    run_id: str
    run_date: date
    slug: str
    headline: str
    one_liner: str
    detailed_markdown: str
    key_points: list[str]
    sources: list[Source]
    fingerprint: str
    seen_again: int = 0
    created_at: datetime | None = None


class UserInfo(BaseModel):
    user_id: int
    username: str


class RunState(BaseModel):
    run_id: str
    user_id: int | None = None
    run_date: date
    topic: str
    kind: str = "daily"
    state: str
    started_at: datetime
    finished_at: datetime | None = None
    trend_count: int = 0
    warnings: int = 0
    last_error: str | None = None
