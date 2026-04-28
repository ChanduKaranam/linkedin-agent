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

# Ensure backend package is importable when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.config import get_settings, get_topic_config
from backend.logging_setup import get_logger, setup_logging
from backend.pipeline import run_pipeline_safe
from backend.storage import (
    create_run,
    get_stale_runs,
    init_db,
    run_exists_for_date,
    update_run_state,
)

log = get_logger(__name__)


async def main() -> int:
    settings = get_settings()
    setup_logging(settings.logs_dir)
    init_db(settings.db_path)

    for stale in get_stale_runs(settings.db_path):
        update_run_state(settings.db_path, stale.run_id, "failed", 0, 0, "INTERRUPTED")
        log.warning("stale_run_marked_failed", run_id=stale.run_id)

    topic_cfg = get_topic_config()
    today = date.today()

    force = "--force" in sys.argv
    if not force and run_exists_for_date(settings.db_path, today, topic_cfg.topic):
        log.info("daily_job_skipped_already_ran", date=today.isoformat())
        return 0

    run_id = str(uuid.uuid4())
    create_run(settings.db_path, run_id, today, topic_cfg.topic)
    log.info("daily_job_started", run_id=run_id, date=today.isoformat())

    await run_pipeline_safe(run_id, today, topic_cfg, settings.db_path, settings.cache_dir)

    from backend.storage import get_run
    run = get_run(settings.db_path, run_id)
    if run and run.state.startswith("completed"):
        log.info("daily_job_finished", run_id=run_id, state=run.state, trends=run.trend_count)
        return 0
    log.error("daily_job_failed", run_id=run_id, error=run.last_error if run else "unknown")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
