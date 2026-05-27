from __future__ import annotations

import json
import re
import time
from collections import deque
from datetime import date
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.chat_agent import answer as chat_answer, answer_stream, build_system_prompt
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
from .deps_auth import CurrentUser
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
_IP_MAX_ENTRIES = 5000  # evict oldest entries beyond this to bound memory
_ip_timestamps: dict[str, deque[float]] = {}
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
    if ip not in _ip_timestamps:
        # Evict oldest IP entry if we're at the cap
        if len(_ip_timestamps) >= _IP_MAX_ENTRIES:
            oldest_ip = next(iter(_ip_timestamps))
            del _ip_timestamps[oldest_ip]
        _ip_timestamps[ip] = deque()
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
async def get_daily_chat(date: str, slug: str, session: SessionDep, current_user: CurrentUser) -> list[ChatMessageOut]:
    try:
        run_date = _date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    rows = await list_chat_messages(session, current_user.user_id, run_date=run_date, slug=slug)
    return [_row_to_msg_out(r) for r in rows]


@router.delete("/chat/{date}/{slug}/messages", response_model=ChatResetOut)
async def delete_daily_chat(date: str, slug: str, session: SessionDep, current_user: CurrentUser) -> ChatResetOut:
    try:
        run_date = _date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    deleted = await delete_chat_messages(session, current_user.user_id, run_date=run_date, slug=slug)
    return ChatResetOut(deleted=deleted)


@router.post("/chat/{date}/{slug}/messages", response_model=ChatPostOut)
async def post_daily_chat(
    date: str, slug: str, body: ChatPostIn, request: Request, session: SessionDep, bg: BackgroundTasks,
    current_user: CurrentUser,
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
    history = await list_chat_messages(session, current_user.user_id, run_date=run_date, slug=slug, limit=cfg.chat.max_history_turns * 2)

    result = await chat_answer(
        trend=trend,
        history=[{"role": r["role"], "content": r["content"]} for r in history],
        user_message=user_content,
        model_str=cfg.models.summarize,
        cache_dir=settings.cache_dir,
        max_tool_calls=cfg.chat.max_tool_calls,
        session=session,
    )

    user_id = await append_chat_message(session, current_user.user_id, trend.run_id, run_date, slug, "user", user_content)
    asst_id = await append_chat_message(
        session, current_user.user_id, trend.run_id, run_date, slug, "assistant",
        result["reply"], result["citations"], result["used_web"],
    )

    await record_sample(session, current_user.user_id, "chat", user_content, source_ref=user_id)
    bg.add_task(_bg_refresh_profile_task, current_user.user_id)

    all_rows = await list_chat_messages(session, current_user.user_id, run_date=run_date, slug=slug, limit=200)
    user_row = next(r for r in all_rows if r["id"] == user_id)
    asst_row = next(r for r in all_rows if r["id"] == asst_id)
    return ChatPostOut(user_message=_row_to_msg_out(user_row), assistant_message=_row_to_msg_out(asst_row))


# ── Daily trend chat (streaming) ───────────────────────────────────────────────

@router.post("/chat/{date}/{slug}/messages/stream")
async def post_daily_chat_stream(
    date: str, slug: str, body: ChatPostIn, request: Request, session: SessionDep,
    current_user: CurrentUser,
) -> StreamingResponse:
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
    history = await list_chat_messages(session, current_user.user_id, run_date=run_date, slug=slug, limit=cfg.chat.max_history_turns * 2)

    # All DB work happens HERE (before streaming) so the session stays clean
    system_prompt = await build_system_prompt(trend, user_content, session)
    user_id = await append_chat_message(session, current_user.user_id, trend.run_id, run_date, slug, "user", user_content)
    await record_sample(session, current_user.user_id, "chat", user_content, source_ref=user_id)
    all_rows = await list_chat_messages(session, current_user.user_id, run_date=run_date, slug=slug, limit=200)
    user_row = next(r for r in all_rows if r["id"] == user_id)
    user_row_dict = _row_to_msg_out(user_row).model_dump()

    history_for_agent = [{"role": r["role"], "content": r["content"]} for r in history]
    run_id = trend.run_id
    run_date_val = run_date

    async def event_stream() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'user_message', 'message': user_row_dict})}\n\n"

        full_reply = ""
        citations: list[dict] = []
        used_web = False
        try:
            async for event_json in answer_stream(
                system_prompt=system_prompt,
                history=history_for_agent,
                user_message=user_content,
                model_str=cfg.models.summarize,
                cache_dir=settings.cache_dir,
                trend=trend,
                max_tool_calls=cfg.chat.max_tool_calls,
            ):
                data = json.loads(event_json)
                if data["type"] == "token":
                    full_reply += data["text"]
                elif data["type"] == "done":
                    citations = data.get("citations", [])
                    used_web = data.get("used_web", False)
                    full_reply = data.get("reply", full_reply)
                yield f"data: {event_json}\n\n"
        except Exception as exc:
            log.error("daily_chat_stream_failed", error=str(exc))
            yield f"data: {json.dumps({'type': 'error', 'detail': 'Generation failed. Please try again.'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        from ..db import _get_factory
        try:
            async with _get_factory()() as new_session:
                asst_id = await append_chat_message(
                    new_session, current_user.user_id, run_id, run_date_val, slug, "assistant", full_reply, citations, used_web
                )
                saved_rows = await list_chat_messages(new_session, current_user.user_id, run_date=run_date_val, slug=slug, limit=200)
                asst_row = next((r for r in saved_rows if r["id"] == asst_id), None)
                if asst_row:
                    yield f"data: {json.dumps({'type': 'assistant_message', 'message': _row_to_msg_out(asst_row).model_dump()})}\n\n"
        except Exception as exc:
            log.error("daily_chat_stream_save_failed", error=str(exc))

        import asyncio
        asyncio.create_task(_bg_refresh_profile_task(current_user.user_id))
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Adhoc/search run chat ───────────────────────────────────────────────────────

@router.get("/chat/runs/{run_id}/{slug}/messages", response_model=list[ChatMessageOut])
async def get_run_chat(run_id: str, slug: str, session: SessionDep, current_user: CurrentUser) -> list[ChatMessageOut]:
    rows = await list_chat_messages(session, current_user.user_id, run_id=run_id, slug=slug)
    return [_row_to_msg_out(r) for r in rows]


@router.delete("/chat/runs/{run_id}/{slug}/messages", response_model=ChatResetOut)
async def delete_run_chat(run_id: str, slug: str, session: SessionDep, current_user: CurrentUser) -> ChatResetOut:
    deleted = await delete_chat_messages(session, current_user.user_id, run_id=run_id, slug=slug)
    return ChatResetOut(deleted=deleted)


@router.post("/chat/runs/{run_id}/{slug}/messages", response_model=ChatPostOut)
async def post_run_chat(
    run_id: str, slug: str, body: ChatPostIn, request: Request, session: SessionDep, bg: BackgroundTasks,
    current_user: CurrentUser,
) -> ChatPostOut:
    _rate_limit_check(_client_ip(request))
    cfg = get_topic_config()
    settings = get_settings()

    trends = await get_trends_for_run(session, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found for this run.")

    user_content = _sanitize_message(body.content)
    history = await list_chat_messages(session, current_user.user_id, run_id=run_id, slug=slug, limit=cfg.chat.max_history_turns * 2)

    result = await chat_answer(
        trend=trend,
        history=[{"role": r["role"], "content": r["content"]} for r in history],
        user_message=user_content,
        model_str=cfg.models.summarize,
        cache_dir=settings.cache_dir,
        max_tool_calls=cfg.chat.max_tool_calls,
        session=session,
    )

    user_id = await append_chat_message(session, current_user.user_id, run_id, trend.run_date, slug, "user", user_content)
    asst_id = await append_chat_message(
        session, current_user.user_id, run_id, trend.run_date, slug, "assistant",
        result["reply"], result["citations"], result["used_web"],
    )

    await record_sample(session, current_user.user_id, "chat", user_content, source_ref=user_id)
    bg.add_task(_bg_refresh_profile_task, current_user.user_id)

    all_rows = await list_chat_messages(session, current_user.user_id, run_id=run_id, slug=slug, limit=200)
    user_row = next(r for r in all_rows if r["id"] == user_id)
    asst_row = next(r for r in all_rows if r["id"] == asst_id)
    return ChatPostOut(user_message=_row_to_msg_out(user_row), assistant_message=_row_to_msg_out(asst_row))


# ── Adhoc/search run chat (streaming) ─────────────────────────────────────────

@router.post("/chat/runs/{run_id}/{slug}/messages/stream")
async def post_run_chat_stream(
    run_id: str, slug: str, body: ChatPostIn, request: Request, session: SessionDep,
    current_user: CurrentUser,
) -> StreamingResponse:
    _rate_limit_check(_client_ip(request))
    cfg = get_topic_config()
    settings = get_settings()

    trends = await get_trends_for_run(session, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found for this run.")

    user_content = _sanitize_message(body.content)
    history = await list_chat_messages(session, current_user.user_id, run_id=run_id, slug=slug, limit=cfg.chat.max_history_turns * 2)

    system_prompt = await build_system_prompt(trend, user_content, session)
    user_id = await append_chat_message(session, current_user.user_id, run_id, trend.run_date, slug, "user", user_content)
    await record_sample(session, current_user.user_id, "chat", user_content, source_ref=user_id)
    all_rows = await list_chat_messages(session, current_user.user_id, run_id=run_id, slug=slug, limit=200)
    user_row = next(r for r in all_rows if r["id"] == user_id)
    user_row_dict = _row_to_msg_out(user_row).model_dump()
    run_date_val = trend.run_date

    history_for_agent = [{"role": r["role"], "content": r["content"]} for r in history]

    async def event_stream() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'user_message', 'message': user_row_dict})}\n\n"

        full_reply = ""
        citations: list[dict] = []
        used_web = False
        try:
            async for event_json in answer_stream(
                system_prompt=system_prompt,
                history=history_for_agent,
                user_message=user_content,
                model_str=cfg.models.summarize,
                cache_dir=settings.cache_dir,
                trend=trend,
                max_tool_calls=cfg.chat.max_tool_calls,
            ):
                data = json.loads(event_json)
                if data["type"] == "token":
                    full_reply += data["text"]
                elif data["type"] == "done":
                    citations = data.get("citations", [])
                    used_web = data.get("used_web", False)
                    full_reply = data.get("reply", full_reply)
                yield f"data: {event_json}\n\n"
        except Exception as exc:
            log.error("run_chat_stream_failed", error=str(exc))
            yield f"data: {json.dumps({'type': 'error', 'detail': 'Generation failed. Please try again.'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        from ..db import _get_factory
        try:
            async with _get_factory()() as new_session:
                asst_id = await append_chat_message(
                    new_session, current_user.user_id, run_id, run_date_val, slug, "assistant", full_reply, citations, used_web
                )
                saved_rows = await list_chat_messages(new_session, current_user.user_id, run_id=run_id, slug=slug, limit=200)
                asst_row = next((r for r in saved_rows if r["id"] == asst_id), None)
                if asst_row:
                    yield f"data: {json.dumps({'type': 'assistant_message', 'message': _row_to_msg_out(asst_row).model_dump()})}\n\n"
        except Exception as exc:
            log.error("run_chat_stream_save_failed", error=str(exc))

        import asyncio
        asyncio.create_task(_bg_refresh_profile_task(current_user.user_id))
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Insights ────────────────────────────────────────────────────────────────────

@router.get("/insights/all", response_model=list[InsightListItemOut])
async def get_all_insights(session: SessionDep, current_user: CurrentUser, limit: int = 300) -> list[InsightListItemOut]:
    rows = await list_all_insights(session, current_user.user_id, limit=min(limit, 1000))
    return [InsightListItemOut(**r) for r in rows]

@router.get("/insights/{date}/{slug}", response_model=list[InsightOut])
async def get_daily_insights(date: str, slug: str, session: SessionDep, current_user: CurrentUser) -> list[InsightOut]:
    try:
        run_date = _date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    rows = await list_insights(session, current_user.user_id, run_date=run_date, slug=slug)
    return [InsightOut(**r) for r in rows]


@router.post("/insights/{date}/{slug}", response_model=InsightOut, status_code=201)
async def post_daily_insight(date: str, slug: str, body: InsightIn, session: SessionDep, current_user: CurrentUser) -> InsightOut:
    try:
        run_date = _date_parse(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    trend = await get_trend_by_slug(session, run_date, slug)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found.")
    insight_id = await create_insight(session, current_user.user_id, trend.run_id, run_date, slug, body.user_perspective, body.summary, body.tags)
    await record_sample(session, current_user.user_id, "insight", body.user_perspective, source_ref=insight_id)
    rows = await list_insights(session, current_user.user_id, run_date=run_date, slug=slug)
    row = next(r for r in rows if r["id"] == insight_id)
    return InsightOut(**row)


@router.get("/insights/runs/{run_id}/{slug}", response_model=list[InsightOut])
async def get_run_insights(run_id: str, slug: str, session: SessionDep, current_user: CurrentUser) -> list[InsightOut]:
    rows = await list_insights(session, current_user.user_id, run_id=run_id, slug=slug)
    return [InsightOut(**r) for r in rows]


@router.post("/insights/runs/{run_id}/{slug}", response_model=InsightOut, status_code=201)
async def post_run_insight(run_id: str, slug: str, body: InsightIn, session: SessionDep, current_user: CurrentUser) -> InsightOut:
    trends = await get_trends_for_run(session, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found for this run.")
    insight_id = await create_insight(session, current_user.user_id, run_id, trend.run_date, slug, body.user_perspective, body.summary, body.tags)
    await record_sample(session, current_user.user_id, "insight", body.user_perspective, source_ref=insight_id)
    rows = await list_insights(session, current_user.user_id, run_id=run_id, slug=slug)
    row = next(r for r in rows if r["id"] == insight_id)
    return InsightOut(**row)


def _date_parse(s: str) -> date:
    return date.fromisoformat(s)


async def _bg_refresh_profile_task(user_id: int) -> None:
    from ..db import _get_factory
    try:
        async with _get_factory()() as session:
            await refresh_profile_if_stale(session, user_id)
    except Exception as exc:
        log.warning("bg_style_profile_refresh_failed", error=str(exc))
