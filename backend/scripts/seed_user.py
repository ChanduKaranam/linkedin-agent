"""Seed a user into the users table.

Usage:
    python -m backend.scripts.seed_user <username> <password>
"""
from __future__ import annotations

import asyncio
import sys

from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import get_settings

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed(username: str, password: str) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    hashed = _pwd_ctx.hash(password)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (username, password) VALUES (:u, :p) "
                "ON CONFLICT (username) DO UPDATE SET password = EXCLUDED.password"
            ),
            {"u": username, "p": hashed},
        )
    await engine.dispose()
    print(f"User '{username}' seeded successfully.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m backend.scripts.seed_user <username> <password>")
        sys.exit(1)
    asyncio.run(seed(sys.argv[1], sys.argv[2]))
