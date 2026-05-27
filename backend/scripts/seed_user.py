"""Seed users into the users table.

Usage:
    python scripts/seed_user.py <username>         # prompts for password
    python scripts/seed_user.py <user>:<pass> [...] # non-interactive
"""
from __future__ import annotations

import asyncio
import getpass
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Allow running as: python scripts/seed_user.py ...
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from src.backend.auth_password import hash_password
from src.backend.config import get_settings


async def seed(username: str, password: str) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    hashed = hash_password(password)
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
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_user.py <username> [<username> ...]")
        print("       python scripts/seed_user.py <username>:<password> [...]")
        sys.exit(1)

    users: list[tuple[str, str]] = []

    for arg in sys.argv[1:]:
        if ":" in arg:
            username, password = arg.split(":", 1)
            users.append((username, password))
        else:
            username = arg
            password = getpass.getpass(f"Password for '{username}': ")
            if not password:
                print("Password cannot be empty.")
                sys.exit(1)
            users.append((username, password))

    async def seed_all():
        for username, password in users:
            await seed(username, password)

    asyncio.run(seed_all())
