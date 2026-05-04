"""
Standalone entry point for Windows Task Scheduler.
Run as: python -m backend.scheduler.daily_job
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.config import get_settings, get_topic_config
from backend.db import _get_factory, dispose_engine
from backend.logging_setup import get_logger, setup_logging
from backend.pipeline import run_pipeline_safe
from backend.storage import (
    create_run,
    get_run,
    get_stale_runs,
    init_db,
    run_exists_for_date,
    update_run_state,
)

log = get_logger(__name__)


async def main() -> int:
    settings = get_settings()
    setup_logging(settings.logs_dir)
    await init_db()

    async with _get_factory()() as session:
        for stale in await get_stale_runs(session):
            await update_run_state(session, stale.run_id, "failed", 0, 0, "INTERRUPTED")
            log.warning("stale_run_marked_failed", run_id=stale.run_id)

        topic_cfg = get_topic_config()
        today = date.today()
        force = "--force" in sys.argv

        if not force and await run_exists_for_date(session, today, topic_cfg.topic):
            log.info("daily_job_skipped_already_ran", date=today.isoformat())
            await dispose_engine()
            return 0

        run_id = str(uuid.uuid4())
        await create_run(session, run_id, today, topic_cfg.topic)

    log.info("daily_job_started", run_id=run_id, date=today.isoformat())

    async with _get_factory()() as session:
        await run_pipeline_safe(session, run_id, today, topic_cfg, settings.cache_dir)
        run = await get_run(session, run_id)

    await dispose_engine()

    if run and run.state.startswith("completed"):
        log.info("daily_job_finished", run_id=run_id, state=run.state, trends=run.trend_count)
        return 0
    log.error("daily_job_failed", run_id=run_id, error=run.last_error if run else "unknown")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
