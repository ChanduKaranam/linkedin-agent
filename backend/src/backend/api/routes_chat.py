from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from datetime import date

from fastapi import APIRouter, HTTPException, Request

from ..agent.chat_agent import answer as chat_answer
from ..config import get_settings, get_topic_config
from ..logging_setup import get_logger
from ..storage import (
    append_chat_message,
    create_insight,
    get_trend_by_slug,
    get_trends_for_run,
    list_chat_messages,
    list_insights,
)
from .schemas import (
    ChatMessageOut,
    ChatPostIn,
    ChatPostOut,
    CitationOut,
    InsightIn,
    InsightOut,
)

router = APIRouter()
log = get_logger(__name__)

_RATE_LIMIT = 30
_RATE_WINDOW = 3600
_ip_timestamps: dict[str, deque[float]] = defaultdict(deque)

_INJECTION_RE = re.compile(r"<SOURCES>|</SOURCES>|<INST>|<SYS>|\[INST\]|\[SYS\]", re.IGNORECASE)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit_check(ip: str) -> None:
    now = time.monotonic()
    window_start = now - _RATE_WINDOW
    q = _ip_timestamps[ip]
    while q and q[0] < window_start:
        q.popleft()
    if len(q) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Too many messages. Maximum {_RATE_LIMIT} per hour.",
            headers={"Retry-After": str(_RATE_WINDOW)},
        )
    q.append(now)


def _sanitize_message(content: str) -> str:
    if _INJECTION_RE.search(content):
        raise HTTPException(status_code=400, detail="Message contains invalid characters.")
    return content.strip()


def _row_to_msg_out(row: dict) -> ChatMessageOut:
    return ChatMessageOut(
        id=row["id"],
        role=row["role"],
        content=row["content"],
        citations=[CitationOut(**c) for c in row["citations"]],
        used_web=row["used_web"],
        created_at=row["created_at"],
    )


# ── Daily trend chat ────────────────────────────────────────────────────────────

@router.get("/chat/{date}/{slug}/messages", response_model=list[ChatMessageOut])
async def get_daily_chat(date: str, slug: str) -> list[ChatMessageOut]:
    settings = get_settings()
    try:
        run_date = date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    rows = list_chat_messages(settings.db_path, run_date=run_date, slug=slug)
    return [_row_to_msg_out(r) for r in rows]


@router.post("/chat/{date}/{slug}/messages", response_model=ChatPostOut)
async def post_daily_chat(date: str, slug: str, body: ChatPostIn, request: Request) -> ChatPostOut:
    _rate_limit_check(_client_ip(request))
    settings = get_settings()
    cfg = get_topic_config()

    try:
        run_date = date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    trend = get_trend_by_slug(settings.db_path, run_date, slug)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found.")

    user_content = _sanitize_message(body.content)

    history = list_chat_messages(
        settings.db_path, run_date=run_date, slug=slug,
        limit=cfg.chat.max_history_turns * 2,
    )

    result = await chat_answer(
        trend=trend,
        history=[{"role": r["role"], "content": r["content"]} for r in history],
        user_message=user_content,
        model_str=cfg.models.summarize,
        cache_dir=settings.cache_dir,
        max_tool_calls=cfg.chat.max_tool_calls,
        source_chars_per_doc=cfg.chat.source_chars_per_doc,
    )

    user_id = append_chat_message(
        settings.db_path, trend.run_id, run_date, slug, "user", user_content,
    )
    asst_id = append_chat_message(
        settings.db_path, trend.run_id, run_date, slug, "assistant",
        result["reply"], result["citations"], result["used_web"],
    )

    user_rows = list_chat_messages(settings.db_path, run_date=run_date, slug=slug, limit=200)
    user_row = next(r for r in user_rows if r["id"] == user_id)
    asst_row = next(r for r in user_rows if r["id"] == asst_id)

    return ChatPostOut(
        user_message=_row_to_msg_out(user_row),
        assistant_message=_row_to_msg_out(asst_row),
    )


# ── Adhoc/search run chat ───────────────────────────────────────────────────────

@router.get("/chat/runs/{run_id}/{slug}/messages", response_model=list[ChatMessageOut])
async def get_run_chat(run_id: str, slug: str) -> list[ChatMessageOut]:
    settings = get_settings()
    rows = list_chat_messages(settings.db_path, run_id=run_id, slug=slug)
    return [_row_to_msg_out(r) for r in rows]


@router.post("/chat/runs/{run_id}/{slug}/messages", response_model=ChatPostOut)
async def post_run_chat(run_id: str, slug: str, body: ChatPostIn, request: Request) -> ChatPostOut:
    _rate_limit_check(_client_ip(request))
    settings = get_settings()
    cfg = get_topic_config()

    trends = get_trends_for_run(settings.db_path, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found for this run.")

    user_content = _sanitize_message(body.content)

    history = list_chat_messages(
        settings.db_path, run_id=run_id, slug=slug,
        limit=cfg.chat.max_history_turns * 2,
    )

    result = await chat_answer(
        trend=trend,
        history=[{"role": r["role"], "content": r["content"]} for r in history],
        user_message=user_content,
        model_str=cfg.models.summarize,
        cache_dir=settings.cache_dir,
        max_tool_calls=cfg.chat.max_tool_calls,
        source_chars_per_doc=cfg.chat.source_chars_per_doc,
    )

    user_id = append_chat_message(
        settings.db_path, run_id, trend.run_date, slug, "user", user_content,
    )
    asst_id = append_chat_message(
        settings.db_path, run_id, trend.run_date, slug, "assistant",
        result["reply"], result["citations"], result["used_web"],
    )

    all_rows = list_chat_messages(settings.db_path, run_id=run_id, slug=slug, limit=200)
    user_row = next(r for r in all_rows if r["id"] == user_id)
    asst_row = next(r for r in all_rows if r["id"] == asst_id)

    return ChatPostOut(
        user_message=_row_to_msg_out(user_row),
        assistant_message=_row_to_msg_out(asst_row),
    )


# ── Insights ────────────────────────────────────────────────────────────────────

@router.get("/insights/{date}/{slug}", response_model=list[InsightOut])
async def get_daily_insights(date: str, slug: str) -> list[InsightOut]:
    settings = get_settings()
    try:
        run_date = date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    rows = list_insights(settings.db_path, run_date=run_date, slug=slug)
    return [InsightOut(**r) for r in rows]


@router.post("/insights/{date}/{slug}", response_model=InsightOut, status_code=201)
async def post_daily_insight(date: str, slug: str, body: InsightIn) -> InsightOut:
    settings = get_settings()
    try:
        run_date = date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    trend = get_trend_by_slug(settings.db_path, run_date, slug)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found.")

    insight_id = create_insight(
        settings.db_path, trend.run_id, run_date, slug,
        body.user_perspective, body.summary, body.tags,
    )
    rows = list_insights(settings.db_path, run_date=run_date, slug=slug)
    row = next(r for r in rows if r["id"] == insight_id)
    return InsightOut(**row)


@router.get("/insights/runs/{run_id}/{slug}", response_model=list[InsightOut])
async def get_run_insights(run_id: str, slug: str) -> list[InsightOut]:
    settings = get_settings()
    rows = list_insights(settings.db_path, run_id=run_id, slug=slug)
    return [InsightOut(**r) for r in rows]


@router.post("/insights/runs/{run_id}/{slug}", response_model=InsightOut, status_code=201)
async def post_run_insight(run_id: str, slug: str, body: InsightIn) -> InsightOut:
    settings = get_settings()
    trends = get_trends_for_run(settings.db_path, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found for this run.")

    insight_id = create_insight(
        settings.db_path, run_id, trend.run_date, slug,
        body.user_perspective, body.summary, body.tags,
    )
    rows = list_insights(settings.db_path, run_id=run_id, slug=slug)
    row = next(r for r in rows if r["id"] == insight_id)
    return InsightOut(**row)


def date_parse(s: str) -> date:
    return date.fromisoformat(s)
