from __future__ import annotations

# Windows fixes — must run before any event loop or I/O stream is created.
import os
import sys

if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings, get_topic_config
from ..db import _get_factory, dispose_engine
from ..logging_setup import get_logger, log_worker_metrics, setup_logging, start_log_worker, stop_log_worker
from ..pipeline import run_pipeline_safe
from ..storage import count_trends_for_run, create_run, get_stale_runs, init_db, purge_data_older_than, purge_expired_sessions, purge_old_logs, run_exists_for_date, update_run_state
from .deps_auth import require_user
from .routes_admin import router as admin_router
from .routes_auth import router as auth_router
from .routes_chat import router as chat_router
from .routes_posts import router as posts_router
from .routes_search import router as search_router
from .routes_slack import router as slack_router
from .routes_trends import router as trends_router

log = get_logger(__name__)

_active_scheduler = None
_run_lock = asyncio.Lock()  # prevents concurrent daily runs (catch-up + APScheduler race)
_catchup_task: asyncio.Task | None = None
_STALE_RUN_TIMEOUT_HOURS = 2  # runs stuck in-progress longer than this are auto-failed
_RETENTION_DAYS = 15  # keep this many days of daily trend data; older data is purged


def _runtime_metrics() -> dict[str, int | float]:
    rss_mb = 0.0
    try:
        import resource  # Unix (Render)
        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss_mb = round(rss_kb / 1024, 2)
    except Exception:
        pass
    return {
        "rss_mb": rss_mb,
        **log_worker_metrics(),
    }


async def _resolve_stale_run(session, run) -> None:
    """Mark a stuck run completed_with_warnings if it has trends, otherwise failed."""
    trend_count = await count_trends_for_run(session, run.run_id)
    if trend_count > 0:
        await update_run_state(session, run.run_id, "completed_with_warnings", trend_count, 0,
                               "Run timed out after persisting partial trends")
        log.warning("stale_run_completed_partial", run_id=run.run_id, state=run.state, trends=trend_count)
    else:
        await update_run_state(session, run.run_id, "failed", 0, 0, "TIMEOUT: run exceeded 2-hour limit")
        log.warning("stale_run_timed_out", run_id=run.run_id, state=run.state)


async def _cleanup_stale_runs() -> None:
    """Mark any in-progress run older than _STALE_RUN_TIMEOUT_HOURS as completed or failed."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_STALE_RUN_TIMEOUT_HOURS)
    async with _get_factory()() as session:
        stale = await get_stale_runs(session)
        for run in stale:
            started = run.started_at
            if started is None:
                continue
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if started < cutoff:
                await _resolve_stale_run(session, run)
    log.info("stale_run_cleanup_complete", **_runtime_metrics())


async def _purge_old_data() -> None:
    """Delete runs/trends/chunks/chat_messages/insights older than _RETENTION_DAYS days.

    Generated posts, style samples, and the style profile are never purged here —
    they outlive the trend window by design.
    """
    import pytz
    from datetime import timedelta
    topic_cfg = get_topic_config()
    tz = pytz.timezone(topic_cfg.timezone)
    today_local = datetime.now(tz).date()
    cutoff = today_local - timedelta(days=_RETENTION_DAYS)
    async with _get_factory()() as session:
        counts = await purge_data_older_than(session, cutoff)
        log_counts = await purge_old_logs(session)
        expired_sessions = await purge_expired_sessions(session)
    log.info(
        "data_retention_purge",
        cutoff=cutoff.isoformat(),
        retention_days=_RETENTION_DAYS,
        expired_sessions=expired_sessions,
        **counts,
        **log_counts,
        **_runtime_metrics(),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _active_scheduler, _catchup_task
    settings = get_settings()
    setup_logging(settings.logs_dir)

    await init_db()
    await start_log_worker()

    # Purge trend data older than retention window on every startup (catch-up for downtime)
    try:
        await _purge_old_data()
    except Exception as exc:
        log.warning("startup_retention_purge_failed", error=str(exc))

    # Mark stale in-progress runs from a previous crash — save any partial trends
    async with _get_factory()() as session:
        for stale in await get_stale_runs(session):
            await _resolve_stale_run(session, stale)

    os.environ.setdefault("LITELLM_REQUEST_TIMEOUT", str(settings.litellm_request_timeout))

    scheduler = None
    if settings.enable_inprocess_scheduler and settings.run_pipeline_in_web_process:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        topic_cfg = get_topic_config()
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            _scheduled_run,
            CronTrigger(
                hour=topic_cfg.schedule_hour,
                minute=topic_cfg.schedule_minute,
                timezone=topic_cfg.timezone,
            ),
            id="daily_trend_run",
            replace_existing=True,
        )
        # Clean up runs that got stuck in-progress (e.g. LLM timeout, process hang)
        scheduler.add_job(
            _cleanup_stale_runs,
            "interval",
            minutes=30,
            id="stale_run_cleanup",
            replace_existing=True,
        )
        # Purge trend data older than _RETENTION_DAYS — runs 1 hour before daily pipeline
        scheduler.add_job(
            _purge_old_data,
            CronTrigger(
                hour=max(topic_cfg.schedule_hour - 1, 0),
                minute=topic_cfg.schedule_minute,
                timezone=topic_cfg.timezone,
            ),
            id="data_retention",
            replace_existing=True,
        )
        scheduler.start()
        _active_scheduler = scheduler
        log.info(
            "inprocess_scheduler_started",
            hour=topic_cfg.schedule_hour,
            minute=topic_cfg.schedule_minute,
            tz=topic_cfg.timezone,
        )

        import pytz
        tz = pytz.timezone(topic_cfg.timezone)
        now_local = datetime.now(tz)
        scheduled_today = now_local.replace(
            hour=topic_cfg.schedule_hour,
            minute=topic_cfg.schedule_minute,
            second=0, microsecond=0,
        )
        async with _get_factory()() as session:
            if now_local >= scheduled_today and not await run_exists_for_date(
                session, date.today(), topic_cfg.topic
            ):
                log.info("catchup_run_triggered", reason="server_started_after_schedule_time")
                _catchup_task = asyncio.create_task(_scheduled_run())
                _catchup_task.add_done_callback(
                    lambda t: t.exception() and log.error("catchup_run_failed", error=str(t.exception()))
                )
    elif settings.enable_inprocess_scheduler and not settings.run_pipeline_in_web_process:
        log.warning("scheduler_disabled_in_web_process", reason="run_pipeline_in_web_process=false")

    yield

    _active_scheduler = None
    if scheduler:
        scheduler.shutdown(wait=False)
    await stop_log_worker()
    await dispose_engine()


async def _scheduled_run() -> None:
    if _run_lock.locked():
        log.info("scheduled_run_skipped_already_running")
        return

    async with _run_lock:
        settings = get_settings()
        topic_cfg = get_topic_config()
        today = date.today()

        async with _get_factory()() as session:
            if await run_exists_for_date(session, today, topic_cfg.topic):
                log.info("scheduled_run_skipped_already_exists", date=today.isoformat())
                return

            run_id = str(uuid.uuid4())
            await create_run(session, run_id, today, topic_cfg.topic)

        log.info("scheduled_run_started", run_id=run_id, date=today.isoformat())

        async with _get_factory()() as session:
            await run_pipeline_safe(session, run_id, today, topic_cfg, settings.cache_dir)


app = FastAPI(
    title="Trend Agent API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if get_settings().debug else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

_protected = {"dependencies": [Depends(require_user)]}

app.include_router(auth_router)
app.include_router(trends_router, **_protected)
app.include_router(admin_router, **_protected)
app.include_router(search_router, **_protected)
app.include_router(chat_router, **_protected)
app.include_router(posts_router, **_protected)
app.include_router(slack_router, **_protected)
