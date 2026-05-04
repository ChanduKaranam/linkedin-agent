"""Delete today's daily run (+ cascaded trends/chunks) and immediately re-trigger the pipeline."""
import asyncio
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

# Make sure the backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.config import get_settings, get_topic_config
from backend.db_models import Run
from backend.pipeline import run_pipeline_safe
from backend.storage import create_run


async def main() -> None:
    settings = get_settings()
    topic_cfg = get_topic_config()
    today = date.today()

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        # Find today's daily run(s)
        rows = (await session.execute(
            select(Run).where(Run.run_date == today, Run.kind == "daily")
        )).scalars().all()

        if rows:
            for row in rows:
                print(f"Deleting run {row.run_id} (state={row.state}, trends={row.trend_count})")
                await session.delete(row)
            await session.commit()
            print(f"Deleted {len(rows)} run(s) for {today}. Trends/chunks cascade-deleted.")
        else:
            print(f"No daily run found for {today} — nothing to delete.")

        # Create a fresh run and fire the pipeline
        run_id = str(uuid.uuid4())
        await create_run(session, run_id, today, topic_cfg.topic)
        print(f"\nStarting fresh pipeline run {run_id} …")

    async with factory() as session:
        await run_pipeline_safe(session, run_id, today, topic_cfg, settings.cache_dir)

    print("\nDone. Restart the backend to serve the new trends.")
    await engine.dispose()


if __name__ == "__main__":
    import os
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())
