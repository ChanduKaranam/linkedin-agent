from __future__ import annotations

import re
import time
import uuid
from collections import defaultdict, deque
from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings, get_topic_config
from ..db import _get_factory, get_session
from ..logging_setup import get_logger
from ..pipeline import build_adhoc_topic_config, run_search_synthesis_safe
from ..storage import create_run, find_adhoc_run, get_run, get_trends_for_run, list_adhoc_runs
from .schemas import SearchHistoryItem, SearchRequest, SearchResponse, SearchRunStatus, TrendDetailOut, TrendListItem

router = APIRouter()
log = get_logger(__name__)

_RATE_LIMIT = 20
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
            detail=f"Too many searches. Maximum {_RATE_LIMIT} per hour.",
            headers={"Retry-After": str(_RATE_WINDOW)},
        )
    q.append(now)


def _validate_topic(topic: str) -> str:
    cleaned = topic.strip()
    if len(cleaned) < 3:
        raise HTTPException(status_code=400, detail="Topic must be at least 3 characters.")
    if len(cleaned) > 200:
        raise HTTPException(status_code=400, detail="Topic must be 200 characters or fewer.")
    if cleaned.replace(" ", "").isnumeric():
        raise HTTPException(status_code=400, detail="Topic must contain text, not just numbers.")
    if _INJECTION_RE.search(cleaned):
        raise HTTPException(status_code=400, detail="Topic contains invalid characters.")
    return cleaned


async def _run_search_background(run_id: str, run_date: date, topic_cfg, cache_dir) -> None:
    async with _get_factory()() as session:
        await run_search_synthesis_safe(session, run_id, run_date, topic_cfg, cache_dir)


@router.post("/search", response_model=SearchResponse, status_code=202)
async def search(
    body: SearchRequest, request: Request, background_tasks: BackgroundTasks, session: SessionDep
) -> SearchResponse:
    _rate_limit_check(_client_ip(request))
    topic = _validate_topic(body.topic)
    today = date.today()
    settings = get_settings()

    if not body.force:
        cached = await find_adhoc_run(session, topic, today)
        if cached:
            is_done = cached.state in ("completed", "completed_with_warnings")
            log.info("search_cache_hit", topic=topic, run_id=cached.run_id, state=cached.state)
            return SearchResponse(run_id=cached.run_id, run_date=today, topic=topic, cached=is_done)

    stored_topic = topic if not body.force else f"{topic}#{int(time.time() * 1000)}"
    run_id = str(uuid.uuid4())
    base_cfg = get_topic_config()
    adhoc_cfg = build_adhoc_topic_config(topic, base_cfg)

    await create_run(session, run_id, today, stored_topic, kind="adhoc")
    background_tasks.add_task(_run_search_background, run_id, today, adhoc_cfg, settings.cache_dir)
    log.info("search_run_started", topic=topic, run_id=run_id, force=body.force)
    return SearchResponse(run_id=run_id, run_date=today, topic=topic, cached=False)


@router.get("/search/history", response_model=list[SearchHistoryItem])
async def search_history(session: SessionDep, limit: int = 50) -> list[SearchHistoryItem]:
    runs = await list_adhoc_runs(session, limit=limit)
    return [
        SearchHistoryItem(
            run_id=r.run_id,
            topic=r.topic.split("#")[0],
            run_date=r.run_date,
            state=r.state,
            trend_count=r.trend_count,
            started_at=r.started_at,
        )
        for r in runs
    ]


@router.get("/search/runs/{run_id}", response_model=SearchRunStatus)
async def search_run_status(run_id: str, session: SessionDep) -> SearchRunStatus:
    run = await get_run(session, run_id)
    if not run or run.kind != "adhoc":
        raise HTTPException(status_code=404, detail="Search run not found.")
    return SearchRunStatus(
        run_id=run.run_id,
        topic=run.topic.split("#")[0],
        state=run.state,
        trend_count=run.trend_count,
        last_error=run.last_error,
    )


@router.get("/search/runs/{run_id}/trends", response_model=list[TrendListItem])
async def search_run_trends(run_id: str, session: SessionDep) -> list[TrendListItem]:
    run = await get_run(session, run_id)
    if not run or run.kind != "adhoc":
        raise HTTPException(status_code=404, detail="Search run not found.")
    trends = await get_trends_for_run(session, run_id)
    return [
        TrendListItem(slug=t.slug, headline=t.headline, one_liner=t.one_liner, source_count=len(t.sources))
        for t in trends
    ]


@router.get("/search/runs/{run_id}/trends/{slug}", response_model=TrendDetailOut)
async def search_run_trend_detail(run_id: str, slug: str, session: SessionDep) -> TrendDetailOut:
    run = await get_run(session, run_id)
    if not run or run.kind != "adhoc":
        raise HTTPException(status_code=404, detail="Search run not found.")
    trends = await get_trends_for_run(session, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found.")
    return TrendDetailOut(
        slug=trend.slug,
        run_date=trend.run_date,
        headline=trend.headline,
        one_liner=trend.one_liner,
        detailed_markdown=trend.detailed_markdown,
        key_points=trend.key_points,
        sources=[s.model_dump() for s in trend.sources],
    )
