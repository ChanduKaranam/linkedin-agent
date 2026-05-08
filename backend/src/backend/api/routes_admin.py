from __future__ import annotations

import time
import uuid
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_schedule_info, get_settings, get_topic_config, update_schedule
from ..db import _get_factory, get_session
from ..logging_setup import get_logger
from ..pipeline import run_pipeline_safe
from ..storage import create_run, get_log_events, get_run, list_runs, run_exists_for_date
from .schemas import LogEventOut, RunNowOut, RunOut, ScheduleOut, ScheduleUpdate

router = APIRouter()
log = get_logger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_schedule_cache: tuple[Any, float] | None = None
_SCHEDULE_TTL = 30.0


@router.get("/admin/schedule", response_model=ScheduleOut)
async def get_schedule_admin() -> ScheduleOut:
    global _schedule_cache
    if _schedule_cache and time.monotonic() < _schedule_cache[1]:
        return _schedule_cache[0]
    value = ScheduleOut(**get_schedule_info())
    _schedule_cache = (value, time.monotonic() + _SCHEDULE_TTL)
    return value


@router.post("/admin/schedule", response_model=ScheduleOut)
async def update_schedule_endpoint(body: ScheduleUpdate) -> ScheduleOut:
    global _schedule_cache
    _schedule_cache = None  # invalidate on write
    update_schedule(body.hour, body.minute)
    try:
        from .main import _active_scheduler
        if _active_scheduler and _active_scheduler.running:
            from apscheduler.triggers.cron import CronTrigger
            cfg = get_topic_config()
            _active_scheduler.reschedule_job(
                "daily_trend_run",
                trigger=CronTrigger(
                    hour=cfg.schedule_hour,
                    minute=cfg.schedule_minute,
                    timezone=cfg.timezone,
                ),
            )
            log.info("scheduler_rescheduled_live", hour=cfg.schedule_hour, minute=cfg.schedule_minute)
    except Exception as exc:
        log.warning("scheduler_reschedule_failed", error=str(exc))
    return ScheduleOut(**get_schedule_info())


async def _run_pipeline_background(run_id: str, run_date: date, topic_cfg, cache_dir) -> None:
    async with _get_factory()() as session:
        await run_pipeline_safe(session, run_id, run_date, topic_cfg, cache_dir)


@router.post("/admin/run-now", response_model=RunNowOut)
async def run_now(
    session: SessionDep, background_tasks: BackgroundTasks, force: bool = False
) -> RunNowOut:
    settings = get_settings()
    topic_cfg = get_topic_config()
    today = date.today()

    if not force and await run_exists_for_date(session, today, topic_cfg.topic):
        raise HTTPException(
            status_code=409,
            detail="A run for today already exists. Pass ?force=true to override.",
        )

    run_id = str(uuid.uuid4())
    await create_run(session, run_id, today, topic_cfg.topic)
    if settings.run_pipeline_in_web_process:
        background_tasks.add_task(_run_pipeline_background, run_id, today, topic_cfg, settings.cache_dir)
        log.info("run_triggered_via_api", run_id=run_id)
        return RunNowOut(run_id=run_id, message="Pipeline started")
    log.info("run_queued_via_api", run_id=run_id)
    return RunNowOut(run_id=run_id, message="Run queued for worker")


@router.get("/admin/runs/{run_id}", response_model=RunOut)
async def get_run_status(run_id: str, session: SessionDep) -> RunOut:
    run = await get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunOut(**run.model_dump())


@router.get("/admin/runs", response_model=list[RunOut])
async def list_runs_endpoint(session: SessionDep, limit: int = Query(default=20, le=100)) -> list[RunOut]:
    runs = await list_runs(session, limit=limit)
    return [RunOut(**r.model_dump()) for r in runs]


@router.get("/admin/logs", response_model=list[LogEventOut])
async def get_logs(
    session: SessionDep,
    level: str | None = Query(default=None, description="Filter by level: DEBUG/INFO/WARNING/ERROR/CRITICAL"),
    logger: str | None = Query(default=None, description="Substring match on logger_name"),
    since: datetime | None = Query(default=None, description="ISO timestamp lower bound"),
    q: str | None = Query(default=None, description="Substring match on event or message"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[LogEventOut]:
    rows = await get_log_events(session, level=level, logger_name=logger, since=since, q=q, limit=limit, offset=offset)
    return [LogEventOut(
        id=r.id, ts=r.ts, level=r.level, logger_name=r.logger_name,
        event=r.event, message=r.message, data=r.data, run_id=r.run_id,
    ) for r in rows]
