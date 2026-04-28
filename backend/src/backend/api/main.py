from __future__ import annotations

# Windows fixes — must run before any event loop or I/O stream is created.
import os
import sys

if sys.platform == "win32":
    # Fix stdout/stderr encoding: Crawl4AI prints Unicode arrows that crash on cp1252.
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    # Fix event loop: SelectorEventLoop can't spawn Playwright subprocesses.
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings, get_topic_config
from ..logging_setup import get_logger, setup_logging
from ..pipeline import run_pipeline_safe
from ..storage import create_run, get_stale_runs, init_db, run_exists_for_date, update_run_state
from .routes_admin import router as admin_router
from .routes_chat import router as chat_router
from .routes_search import router as search_router
from .routes_trends import router as trends_router

log = get_logger(__name__)

# Module-level reference so admin routes can reschedule the live job
_active_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _active_scheduler
    settings = get_settings()
    setup_logging(settings.logs_dir)
    init_db(settings.db_path)

    # Mark any stale in-progress runs from a previous crash
    for stale in get_stale_runs(settings.db_path):
        update_run_state(settings.db_path, stale.run_id, "failed", 0, 0, "INTERRUPTED")
        log.warning("stale_run_marked_failed", run_id=stale.run_id)

    # Set LiteLLM global config
    os.environ.setdefault("LITELLM_REQUEST_TIMEOUT", str(settings.litellm_request_timeout))

    scheduler = None
    if settings.enable_inprocess_scheduler:
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
        scheduler.start()
        _active_scheduler = scheduler
        log.info(
            "inprocess_scheduler_started",
            hour=topic_cfg.schedule_hour,
            minute=topic_cfg.schedule_minute,
            tz=topic_cfg.timezone,
        )

        # Catch-up: if the server starts after today's scheduled time and no run
        # has happened yet, fire immediately so the user isn't stuck until tomorrow.
        import pytz
        tz = pytz.timezone(topic_cfg.timezone)
        now_local = datetime.now(tz)
        scheduled_today = now_local.replace(
            hour=topic_cfg.schedule_hour,
            minute=topic_cfg.schedule_minute,
            second=0, microsecond=0,
        )
        if now_local >= scheduled_today and not run_exists_for_date(
            settings.db_path, date.today(), topic_cfg.topic
        ):
            log.info("catchup_run_triggered", reason="server_started_after_schedule_time")
            asyncio.create_task(_scheduled_run())

    yield

    _active_scheduler = None
    if scheduler:
        scheduler.shutdown(wait=False)


async def _scheduled_run() -> None:
    settings = get_settings()
    topic_cfg = get_topic_config()
    today = date.today()

    if run_exists_for_date(settings.db_path, today, topic_cfg.topic):
        log.info("scheduled_run_skipped_already_exists", date=today.isoformat())
        return

    run_id = str(uuid.uuid4())
    create_run(settings.db_path, run_id, today, topic_cfg.topic)
    log.info("scheduled_run_started", run_id=run_id, date=today.isoformat())
    await run_pipeline_safe(run_id, today, topic_cfg, settings.db_path, settings.cache_dir)


app = FastAPI(
    title="Trend Agent API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if get_settings().debug else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)

app.include_router(trends_router)
app.include_router(admin_router)
app.include_router(search_router)
app.include_router(chat_router)
