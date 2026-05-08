"""Fix today's stuck run — marks it completed_with_warnings if it has trends."""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

async def main() -> None:
    from backend.config import get_settings
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text, update

    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_size=1)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as s:
        stuck = (await s.execute(text(
            "SELECT run_id, run_date, state FROM runs "
            "WHERE state NOT IN ('completed','completed_with_warnings','failed') "
            "ORDER BY started_at DESC LIMIT 5"
        ))).fetchall()

        if not stuck:
            print("No stuck runs found.")
            await engine.dispose()
            return

        for run in stuck:
            count = (await s.execute(text(
                f"SELECT COUNT(*) FROM trends WHERE run_id = '{run.run_id}'"
            ))).scalar()
            print(f"Run {run.run_id[:8]}… | date={run.run_date} | state={run.state} | trends={count}")

            if count > 0:
                from datetime import datetime, timezone
                await s.execute(text(
                    f"UPDATE runs SET state='completed_with_warnings', trend_count={count}, "
                    f"finished_at=NOW(), last_error='Run timed out after persisting {count} trends' "
                    f"WHERE run_id='{run.run_id}'"
                ))
                print(f"  → Marked completed_with_warnings (trend_count={count})")
            else:
                await s.execute(text(
                    f"UPDATE runs SET state='failed', finished_at=NOW(), "
                    f"last_error='TIMEOUT: no trends produced' "
                    f"WHERE run_id='{run.run_id}'"
                ))
                print(f"  → Marked failed (no trends)")
        await s.commit()
        print("Done.")

    await engine.dispose()

asyncio.run(main())
