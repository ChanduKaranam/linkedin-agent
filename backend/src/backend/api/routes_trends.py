from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_schedule_info
from ..db import get_session
from ..logging_setup import get_logger
from ..storage import (
    get_available_dates,
    get_latest_completed_run,
    get_latest_daily_run,
    get_trend_by_slug,
    get_trends_for_date,
)
from .schemas import HealthOut, ScheduleOut, TrendDetailOut, TrendListItem

router = APIRouter()
log = get_logger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/health", response_model=HealthOut)
async def health(session: SessionDep) -> HealthOut:
    """Liveness + latest run status for frontend loading state."""
    from datetime import datetime, timedelta, timezone
    from ..storage import count_trends_for_run
    latest = await get_latest_daily_run(session)
    if latest is None:
        return HealthOut(
            status="ok",
            latest_run_date=None,
            latest_run_state=None,
            pipeline_running=False,
            trend_count=0,
        )
    running_states = {"pending", "discovering", "scraping", "clustering", "summarizing"}
    is_in_progress = latest.state in running_states

    # Only report pipeline_running=True when the run is actively in-progress
    # AND hasn't already produced visible trends. A run stuck for > 2 hours that
    # already has trends should not hide those trends from the frontend.
    pipeline_running = False
    if is_in_progress:
        started = latest.started_at
        if started and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - started if started else timedelta(0)
        has_trends = latest.trend_count > 0 or await count_trends_for_run(session, latest.run_id) > 0
        pipeline_running = not has_trends and age < timedelta(hours=2)

    return HealthOut(
        status="ok",
        latest_run_date=latest.run_date,
        latest_run_state=latest.state,
        pipeline_running=pipeline_running,
        trend_count=latest.trend_count,
    )


@router.get("/schedule", response_model=ScheduleOut)
async def get_schedule() -> ScheduleOut:
    return ScheduleOut(**get_schedule_info())


@router.get("/trends/dates", response_model=list[str])
async def available_dates(session: SessionDep) -> list[str]:
    dates = await get_available_dates(session)
    return [d.isoformat() for d in dates]


@router.get("/trends/today", response_model=list[TrendListItem])
async def trends_today(session: SessionDep) -> list[TrendListItem]:
    run = await get_latest_completed_run(session)
    if not run:
        return []
    trends = await get_trends_for_date(session, run.run_date)
    return [
        TrendListItem(slug=t.slug, headline=t.headline, one_liner=t.one_liner, source_count=len(t.sources))
        for t in trends
    ]


@router.get("/trends/by-date/{run_date}", response_model=list[TrendListItem])
async def trends_by_date(session: SessionDep, run_date: date = Path(...)) -> list[TrendListItem]:
    trends = await get_trends_for_date(session, run_date)
    return [
        TrendListItem(slug=t.slug, headline=t.headline, one_liner=t.one_liner, source_count=len(t.sources))
        for t in trends
    ]


@router.get("/trends/{run_date}/{slug}", response_model=TrendDetailOut)
async def trend_detail(session: SessionDep, run_date: date = Path(...), slug: str = Path(...)) -> TrendDetailOut:
    trend = await get_trend_by_slug(session, run_date, slug)
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    return TrendDetailOut(
        slug=trend.slug,
        run_date=trend.run_date,
        headline=trend.headline,
        one_liner=trend.one_liner,
        detailed_markdown=trend.detailed_markdown,
        key_points=trend.key_points,
        sources=[s.model_dump() for s in trend.sources],
    )
