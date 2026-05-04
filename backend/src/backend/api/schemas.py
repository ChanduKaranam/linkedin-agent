from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class SourceOut(BaseModel):
    url: str
    title: str
    domain: str


class TrendListItem(BaseModel):
    slug: str
    headline: str
    one_liner: str
    source_count: int


class TrendDetailOut(BaseModel):
    slug: str
    run_date: date
    headline: str
    one_liner: str
    detailed_markdown: str
    key_points: list[str]
    sources: list[SourceOut]


class HealthOut(BaseModel):
    status: str
    latest_run_date: date | None
    trend_count: int


class RunOut(BaseModel):
    run_id: str
    run_date: date
    topic: str
    state: str
    started_at: datetime
    finished_at: datetime | None
    trend_count: int
    warnings: int
    last_error: str | None


class RunNowOut(BaseModel):
    run_id: str
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    run_id: str | None = None


class ErrorOut(BaseModel):
    error: ErrorDetail


class SearchRequest(BaseModel):
    topic: str
    force: bool = False


class SearchResponse(BaseModel):
    run_id: str
    run_date: date
    topic: str
    cached: bool


class SearchRunStatus(BaseModel):
    run_id: str
    topic: str
    state: str
    trend_count: int
    last_error: str | None


class ScheduleOut(BaseModel):
    hour: int
    minute: int
    timezone: str


class ScheduleUpdate(BaseModel):
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)


class SearchHistoryItem(BaseModel):
    run_id: str
    topic: str
    run_date: date
    state: str
    trend_count: int
    started_at: datetime


class CitationOut(BaseModel):
    url: str
    title: str
    snippet: str = ""


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: list[CitationOut]
    used_web: bool
    created_at: str


class ChatPostIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ChatPostOut(BaseModel):
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut


class InsightIn(BaseModel):
    user_perspective: str = Field(min_length=1, max_length=8000)
    summary: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=10)


class InsightOut(BaseModel):
    id: int
    user_perspective: str
    summary: str
    tags: list[str]
    created_at: str


class InsightListItemOut(InsightOut):
    run_id: str
    run_date: str
    slug: str
    context_kind: Literal["trend", "search"]
    topic: str
    headline: str


class ChatResetOut(BaseModel):
    deleted: int


class GeneratedPostOut(BaseModel):
    id: int
    kind: Literal["linkedin", "blog"]
    run_id: str
    run_date: str
    slug: str
    content_markdown: str
    tags: list[str]
    status: Literal["draft", "edited", "published"]
    linkedin_post_urn: str | None
    created_at: str
    updated_at: str


class GeneratedPostPatchIn(BaseModel):
    content_markdown: str = Field(min_length=1, max_length=40000)
    tags: list[str] = Field(default_factory=list)


class GeneratePostIn(BaseModel):
    user_instructions: str = Field(default="", max_length=2000)


class LinkedInStatusOut(BaseModel):
    connected: bool
    expires_at: str | None
    member_urn: str | None


class PublishResponseOut(BaseModel):
    post_urn: str
    status: str


class GeneratedPostListItem(GeneratedPostOut):
    headline: str = Field(min_length=1)


class DeletePostOut(BaseModel):
    deleted: bool
