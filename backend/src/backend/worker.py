from __future__ import annotations

import asyncio

from sqlalchemy import select

from .config import get_settings, get_topic_config
from .db import _get_factory, dispose_engine
from .db_models import Run
from .logging_setup import get_logger, setup_logging, start_log_worker, stop_log_worker
from .pipeline import build_adhoc_topic_config, run_pipeline_safe, run_search_synthesis_safe
from .storage import init_db

log = get_logger(__name__)


async def _next_pending_run() -> Run | None:
    async with _get_factory()() as session:
        row = (
            await session.execute(
                select(Run)
                .where(Run.state == "pending")
                .order_by(Run.started_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        row.state = "discovering"
        await session.commit()
        return row


async def _process_run(run: Run) -> None:
    settings = get_settings()
    base_cfg = get_topic_config()
    topic_clean = run.topic.split("#")[0]
    if run.kind == "adhoc":
        cfg = build_adhoc_topic_config(topic_clean, base_cfg)
        async with _get_factory()() as session:
            await run_search_synthesis_safe(session, run.run_id, run.run_date, cfg, settings.cache_dir)
        return

    cfg = base_cfg.model_copy(update={"topic": topic_clean})
    async with _get_factory()() as session:
        await run_pipeline_safe(session, run.run_id, run.run_date, cfg, settings.cache_dir)


async def run_worker() -> None:
    settings = get_settings()
    setup_logging(settings.logs_dir)
    await init_db()
    await start_log_worker()
    log.info("worker_started", poll_seconds=settings.worker_poll_seconds)

    try:
        while True:
            run = await _next_pending_run()
            if run is None:
                await asyncio.sleep(max(settings.worker_poll_seconds, 1))
                continue
            try:
                log.info("worker_processing_run", run_id=run.run_id, kind=run.kind, run_date=run.run_date.isoformat())
                await _process_run(run)
            except Exception as exc:
                log.exception("worker_run_failed", run_id=run.run_id, error=str(exc))
                await asyncio.sleep(1)
    finally:
        await stop_log_worker()
        await dispose_engine()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
