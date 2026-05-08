from __future__ import annotations

import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session
from ..storage import get_session_username

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# token -> (username, expires_epoch, checked_mono)
_auth_cache: dict[str, tuple[str, float, float]] = {}


def invalidate_auth_cache(token: str) -> None:
    _auth_cache.pop(token, None)


async def require_user(request: Request, session: SessionDep) -> str:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")
    now_mono = time.monotonic()
    cached = _auth_cache.get(token)
    if cached is not None:
        username, expires_epoch, checked_mono = cached
        if now_mono - checked_mono <= max(settings.auth_cache_ttl_seconds, 1) and expires_epoch > time.time():
            return username
        _auth_cache.pop(token, None)

    username = await get_session_username(session, token)
    if username is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    # Keep cache entry short-lived; DB is still source of truth.
    _auth_cache[token] = (username, time.time() + 30 * 24 * 3600, now_mono)
    return username


CurrentUser = Annotated[str, Depends(require_user)]
