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
from datetime import date, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings, get_topic_config
from ..db import _get_factory, dispose_engine
from ..logging_setup import get_logger, setup_logging
from ..pipeline import run_pipeline_safe
from ..storage import create_run, get_stale_runs, init_db, run_exists_for_date, update_run_state
from .routes_admin import router as admin_router
from .routes_chat import router as chat_router
from .routes_posts import router as posts_router
from .routes_search import router as search_router
from .routes_slack import router as slack_router
from .routes_trends import router as trends_router

log = get_logger(__name__)

_active_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _active_scheduler
    settings = get_settings()
    setup_logging(settings.logs_dir)

    await init_db()

    # Mark stale in-progress runs from a previous crash
    async with _get_factory()() as session:
        for stale in await get_stale_runs(session):
            await update_run_state(session, stale.run_id, "failed", 0, 0, "INTERRUPTED")
            log.warning("stale_run_marked_failed", run_id=stale.run_id)

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
                asyncio.create_task(_scheduled_run())

    yield

    _active_scheduler = None
    if scheduler:
        scheduler.shutdown(wait=False)
    await dispose_engine()


async def _scheduled_run() -> None:
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
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["*"],
)

app.include_router(trends_router)
app.include_router(admin_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(posts_router)
app.include_router(slack_router)
