from __future__ import annotations

import asyncio
import uuid
from datetime import date, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from ..config import get_schedule_info, get_settings, get_topic_config, update_schedule
from ..logging_setup import get_logger
from ..pipeline import run_pipeline_safe
from ..storage import create_run, get_run, list_runs, run_exists_for_date
from .schemas import RunNowOut, RunOut, ScheduleOut, ScheduleUpdate

router = APIRouter()
log = get_logger(__name__)


def _db():
    return get_settings().db_path


def _guard():
    if not get_settings().debug:
        raise HTTPException(status_code=404)


@router.get("/admin/schedule", response_model=ScheduleOut)
async def get_schedule_admin() -> ScheduleOut:
    """Return the current schedule config (same data as GET /schedule, guarded by DEBUG)."""
    _guard()
    return ScheduleOut(**get_schedule_info())


@router.post("/admin/schedule", response_model=ScheduleOut)
async def update_schedule_endpoint(body: ScheduleUpdate) -> ScheduleOut:
    _guard()
    update_schedule(body.hour, body.minute)

    # Immediately reschedule the live APScheduler job so the new time takes effect
    # without requiring a server restart.
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
            log.info(
                "scheduler_rescheduled_live",
                hour=cfg.schedule_hour,
                minute=cfg.schedule_minute,
            )
    except Exception as exc:
        # Non-fatal: config is already saved to YAML; scheduler will pick it up on restart
        log.warning("scheduler_reschedule_failed", error=str(exc))

    return ScheduleOut(**get_schedule_info())


@router.post("/admin/run-now", response_model=RunNowOut)
async def run_now(background_tasks: BackgroundTasks, force: bool = False) -> RunNowOut:
    _guard()
    settings = get_settings()
    topic_cfg = get_topic_config()
    today = date.today()

    if not force and run_exists_for_date(_db(), today, topic_cfg.topic):
        raise HTTPException(
            status_code=409,
            detail="A run for today already exists. Pass ?force=true to override.",
        )

    run_id = str(uuid.uuid4())
    create_run(_db(), run_id, today, topic_cfg.topic)
    background_tasks.add_task(
        run_pipeline_safe,
        run_id=run_id,
        run_date=today,
        topic_cfg=topic_cfg,
        db_path=_db(),
        cache_dir=settings.cache_dir,
    )
    log.info("run_triggered_via_api", run_id=run_id)
    return RunNowOut(run_id=run_id, message="Pipeline started")


@router.get("/admin/runs/{run_id}", response_model=RunOut)
async def get_run_status(run_id: str) -> RunOut:
    _guard()
    run = get_run(_db(), run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunOut(**run.model_dump())


@router.get("/admin/runs", response_model=list[RunOut])
async def list_runs_endpoint(limit: int = Query(default=20, le=100)) -> list[RunOut]:
    _guard()
    runs = list_runs(_db(), limit=limit)
    return [RunOut(**r.model_dump()) for r in runs]
