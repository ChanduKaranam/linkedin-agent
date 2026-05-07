"""One-off: mark today's stuck summarizing run as completed_with_warnings."""
import asyncio
from datetime import datetime, timezone

import asyncpg

STUCK_RUN_ID = "caf3aebe-3f5f-4be1-8cd7-481ccede072e"
DB_URL = "postgresql://postgres:chandu@localhost:5432/linkedin-agent"


async def main() -> None:
    conn = await asyncpg.connect(DB_URL)
    now = datetime.now(timezone.utc)
    result = await conn.execute(
        """
        UPDATE runs
        SET state = 'completed_with_warnings',
            finished_at = $1,
            trend_count = 3,
            last_error = 'INTERRUPTED: pipeline got stuck at summarizing stage'
        WHERE run_id = $2
        """,
        now, STUCK_RUN_ID,
    )
    print("Updated:", result)

    row = await conn.fetchrow(
        "SELECT run_id, state, trend_count, finished_at FROM runs WHERE run_id = $1",
        STUCK_RUN_ID,
    )
    print("After fix:", dict(row))
    await conn.close()


asyncio.run(main())
