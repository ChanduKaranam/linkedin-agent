"""Quick DB state check — run with: python scripts/_check_db.py"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

async def main() -> None:
    from backend.config import get_settings
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from datetime import datetime
    import pytz

    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_size=1)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as s:
        tz = pytz.timezone("Asia/Kolkata")
        today = datetime.now(tz).date()
        print(f"Today (IST): {today}")
        print(f"Scheduler enabled: {settings.enable_inprocess_scheduler}")

        rows = (await s.execute(text(
            "SELECT run_id, run_date, kind, state, trend_count, warnings, last_error, started_at "
            "FROM runs ORDER BY started_at DESC LIMIT 10"
        ))).fetchall()
        print(f"\nRecent runs ({len(rows)}):")
        for r in rows:
            err = (r.last_error or "")[:80]
            print(f"  {r.run_date} | {r.state:30s} | trends={r.trend_count} | warns={r.warnings} | err={err}")

        count = (await s.execute(text(
            f"SELECT COUNT(*) FROM trends WHERE run_date = '{today}'"
        ))).scalar()
        print(f"\nTrends for today ({today}): {count}")

        dates = [(await s.execute(text(
            "SELECT DISTINCT run_date FROM trends ORDER BY run_date DESC LIMIT 5"
        ))).fetchall()]
        print(f"Available trend dates: {[str(d[0]) for row in dates for d in row]}")

    await engine.dispose()

asyncio.run(main())
