from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.chat_agent import answer as chat_answer
from ..config import get_settings, get_topic_config
from ..db import get_session
from ..logging_setup import get_logger
from ..storage import (
    append_chat_message,
    create_insight,
    delete_chat_messages,
    get_trend_by_slug,
    get_trends_for_run,
    list_all_insights,
    list_chat_messages,
    list_insights,
)
from ..style.collector import record_sample
from ..style.profile import refresh_profile_if_stale
from .schemas import (
    ChatMessageOut,
    ChatResetOut,
    ChatPostIn,
    ChatPostOut,
    CitationOut,
    InsightIn,
    InsightListItemOut,
    InsightOut,
)

router = APIRouter()
log = get_logger(__name__)

_RATE_LIMIT = 30
_RATE_WINDOW = 3600
_ip_timestamps: dict[str, deque[float]] = defaultdict(deque)
_INJECTION_RE = re.compile(r"<SOURCES>|</SOURCES>|<INST>|<SYS>|\[INST\]|\[SYS\]", re.IGNORECASE)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


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
async def get_daily_chat(date: str, slug: str, session: SessionDep) -> list[ChatMessageOut]:
    try:
        run_date = _date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    rows = await list_chat_messages(session, run_date=run_date, slug=slug)
    return [_row_to_msg_out(r) for r in rows]


@router.delete("/chat/{date}/{slug}/messages", response_model=ChatResetOut)
async def delete_daily_chat(date: str, slug: str, session: SessionDep) -> ChatResetOut:
    try:
        run_date = _date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    deleted = await delete_chat_messages(session, run_date=run_date, slug=slug)
    return ChatResetOut(deleted=deleted)


@router.post("/chat/{date}/{slug}/messages", response_model=ChatPostOut)
async def post_daily_chat(
    date: str, slug: str, body: ChatPostIn, request: Request, session: SessionDep, bg: BackgroundTasks
) -> ChatPostOut:
    _rate_limit_check(_client_ip(request))
    cfg = get_topic_config()
    settings = get_settings()

    try:
        run_date = _date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    trend = await get_trend_by_slug(session, run_date, slug)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found.")

    user_content = _sanitize_message(body.content)
    history = await list_chat_messages(session, run_date=run_date, slug=slug, limit=cfg.chat.max_history_turns * 2)

    result = await chat_answer(
        trend=trend,
        history=[{"role": r["role"], "content": r["content"]} for r in history],
        user_message=user_content,
        model_str=cfg.models.summarize,
        cache_dir=settings.cache_dir,
        max_tool_calls=cfg.chat.max_tool_calls,
        session=session,
    )

    user_id = await append_chat_message(session, trend.run_id, run_date, slug, "user", user_content)
    asst_id = await append_chat_message(
        session, trend.run_id, run_date, slug, "assistant",
        result["reply"], result["citations"], result["used_web"],
    )

    await record_sample(session, "chat", user_content, source_ref=user_id)
    bg.add_task(_bg_refresh_profile_task)

    all_rows = await list_chat_messages(session, run_date=run_date, slug=slug, limit=200)
    user_row = next(r for r in all_rows if r["id"] == user_id)
    asst_row = next(r for r in all_rows if r["id"] == asst_id)
    return ChatPostOut(user_message=_row_to_msg_out(user_row), assistant_message=_row_to_msg_out(asst_row))


# ── Adhoc/search run chat ───────────────────────────────────────────────────────

@router.get("/chat/runs/{run_id}/{slug}/messages", response_model=list[ChatMessageOut])
async def get_run_chat(run_id: str, slug: str, session: SessionDep) -> list[ChatMessageOut]:
    rows = await list_chat_messages(session, run_id=run_id, slug=slug)
    return [_row_to_msg_out(r) for r in rows]


@router.delete("/chat/runs/{run_id}/{slug}/messages", response_model=ChatResetOut)
async def delete_run_chat(run_id: str, slug: str, session: SessionDep) -> ChatResetOut:
    deleted = await delete_chat_messages(session, run_id=run_id, slug=slug)
    return ChatResetOut(deleted=deleted)


@router.post("/chat/runs/{run_id}/{slug}/messages", response_model=ChatPostOut)
async def post_run_chat(
    run_id: str, slug: str, body: ChatPostIn, request: Request, session: SessionDep, bg: BackgroundTasks
) -> ChatPostOut:
    _rate_limit_check(_client_ip(request))
    cfg = get_topic_config()
    settings = get_settings()

    trends = await get_trends_for_run(session, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found for this run.")

    user_content = _sanitize_message(body.content)
    history = await list_chat_messages(session, run_id=run_id, slug=slug, limit=cfg.chat.max_history_turns * 2)

    result = await chat_answer(
        trend=trend,
        history=[{"role": r["role"], "content": r["content"]} for r in history],
        user_message=user_content,
        model_str=cfg.models.summarize,
        cache_dir=settings.cache_dir,
        max_tool_calls=cfg.chat.max_tool_calls,
        session=session,
    )

    user_id = await append_chat_message(session, run_id, trend.run_date, slug, "user", user_content)
    asst_id = await append_chat_message(
        session, run_id, trend.run_date, slug, "assistant",
        result["reply"], result["citations"], result["used_web"],
    )

    await record_sample(session, "chat", user_content, source_ref=user_id)
    bg.add_task(_bg_refresh_profile_task)

    all_rows = await list_chat_messages(session, run_id=run_id, slug=slug, limit=200)
    user_row = next(r for r in all_rows if r["id"] == user_id)
    asst_row = next(r for r in all_rows if r["id"] == asst_id)
    return ChatPostOut(user_message=_row_to_msg_out(user_row), assistant_message=_row_to_msg_out(asst_row))


# ── Insights ────────────────────────────────────────────────────────────────────

@router.get("/insights/all", response_model=list[InsightListItemOut])
async def get_all_insights(session: SessionDep, limit: int = 300) -> list[InsightListItemOut]:
    rows = await list_all_insights(session, limit=min(limit, 1000))
    return [InsightListItemOut(**r) for r in rows]

@router.get("/insights/{date}/{slug}", response_model=list[InsightOut])
async def get_daily_insights(date: str, slug: str, session: SessionDep) -> list[InsightOut]:
    try:
        run_date = _date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    rows = await list_insights(session, run_date=run_date, slug=slug)
    return [InsightOut(**r) for r in rows]


@router.post("/insights/{date}/{slug}", response_model=InsightOut, status_code=201)
async def post_daily_insight(date: str, slug: str, body: InsightIn, session: SessionDep) -> InsightOut:
    try:
        run_date = _date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    trend = await get_trend_by_slug(session, run_date, slug)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found.")
    insight_id = await create_insight(session, trend.run_id, run_date, slug, body.user_perspective, body.summary, body.tags)
    await record_sample(session, "insight", body.user_perspective, source_ref=insight_id)
    rows = await list_insights(session, run_date=run_date, slug=slug)
    row = next(r for r in rows if r["id"] == insight_id)
    return InsightOut(**row)


@router.get("/insights/runs/{run_id}/{slug}", response_model=list[InsightOut])
async def get_run_insights(run_id: str, slug: str, session: SessionDep) -> list[InsightOut]:
    rows = await list_insights(session, run_id=run_id, slug=slug)
    return [InsightOut(**r) for r in rows]


@router.post("/insights/runs/{run_id}/{slug}", response_model=InsightOut, status_code=201)
async def post_run_insight(run_id: str, slug: str, body: InsightIn, session: SessionDep) -> InsightOut:
    trends = await get_trends_for_run(session, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found for this run.")
    insight_id = await create_insight(session, run_id, trend.run_date, slug, body.user_perspective, body.summary, body.tags)
    await record_sample(session, "insight", body.user_perspective, source_ref=insight_id)
    rows = await list_insights(session, run_id=run_id, slug=slug)
    row = next(r for r in rows if r["id"] == insight_id)
    return InsightOut(**row)


def _date_parse(s: str) -> date:
    return date.fromisoformat(s)


async def _bg_refresh_profile_task() -> None:
    from ..db import _get_factory
    try:
        async with _get_factory()() as session:
            await refresh_profile_if_stale(session)
    except Exception as exc:
        log.warning("bg_style_profile_refresh_failed", error=str(exc))
