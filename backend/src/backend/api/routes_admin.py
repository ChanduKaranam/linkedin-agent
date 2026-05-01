from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_schedule_info, get_settings, get_topic_config, update_schedule
from ..db import _get_factory, get_session
from ..logging_setup import get_logger
from ..pipeline import run_pipeline_safe
from ..storage import create_run, get_run, list_runs, run_exists_for_date
from .schemas import RunNowOut, RunOut, ScheduleOut, ScheduleUpdate

router = APIRouter()
log = get_logger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _guard():
    if not get_settings().debug:
        raise HTTPException(status_code=404)


@router.get("/admin/schedule", response_model=ScheduleOut)
async def get_schedule_admin() -> ScheduleOut:
    return ScheduleOut(**get_schedule_info())


@router.post("/admin/schedule", response_model=ScheduleOut)
async def update_schedule_endpoint(body: ScheduleUpdate) -> ScheduleOut:
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
    _guard()
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
    background_tasks.add_task(_run_pipeline_background, run_id, today, topic_cfg, settings.cache_dir)
    log.info("run_triggered_via_api", run_id=run_id)
    return RunNowOut(run_id=run_id, message="Pipeline started")


@router.get("/admin/runs/{run_id}", response_model=RunOut)
async def get_run_status(run_id: str, session: SessionDep) -> RunOut:
    _guard()
    run = await get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunOut(**run.model_dump())


@router.get("/admin/runs", response_model=list[RunOut])
async def list_runs_endpoint(session: SessionDep, limit: int = Query(default=20, le=100)) -> list[RunOut]:
    _guard()
    runs = await list_runs(session, limit=limit)
    return [RunOut(**r.model_dump()) for r in runs]
