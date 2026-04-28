from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Path

from ..config import get_settings
from ..logging_setup import get_logger
from ..config import get_schedule_info
from ..storage import get_available_dates, get_latest_completed_run, get_trend_by_slug, get_trends_for_date
from .schemas import HealthOut, ScheduleOut, TrendDetailOut, TrendListItem

router = APIRouter()
log = get_logger(__name__)


def _db():
    return get_settings().db_path


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    run = get_latest_completed_run(_db())
    return HealthOut(
        status="ok",
        latest_run_date=run.run_date if run else None,
        trend_count=run.trend_count if run else 0,
    )


@router.get("/schedule", response_model=ScheduleOut)
async def get_schedule() -> ScheduleOut:
    info = get_schedule_info()
    return ScheduleOut(**info)


@router.get("/trends/dates", response_model=list[str])
async def available_dates() -> list[str]:
    dates = get_available_dates(_db())
    return [d.isoformat() for d in dates]


@router.get("/trends/today", response_model=list[TrendListItem])
async def trends_today() -> list[TrendListItem]:
    run = get_latest_completed_run(_db())
    if not run:
        return []
    trends = get_trends_for_date(_db(), run.run_date)
    return [
        TrendListItem(
            slug=t.slug,
            headline=t.headline,
            one_liner=t.one_liner,
            source_count=len(t.sources),
        )
        for t in trends
    ]


@router.get("/trends/by-date/{run_date}", response_model=list[TrendListItem])
async def trends_by_date(run_date: date = Path(...)) -> list[TrendListItem]:
    trends = get_trends_for_date(_db(), run_date)
    return [
        TrendListItem(
            slug=t.slug,
            headline=t.headline,
            one_liner=t.one_liner,
            source_count=len(t.sources),
        )
        for t in trends
    ]


@router.get("/trends/{run_date}/{slug}", response_model=TrendDetailOut)
async def trend_detail(run_date: date = Path(...), slug: str = Path(...)) -> TrendDetailOut:
    trend = get_trend_by_slug(_db(), run_date, slug)
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
