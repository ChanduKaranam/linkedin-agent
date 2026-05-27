from __future__ import annotations

import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session
from ..models import UserInfo
from ..storage import get_session_user_info

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# token -> (UserInfo, expires_epoch, checked_mono)
_auth_cache: dict[str, tuple[UserInfo, float, float]] = {}


def invalidate_auth_cache(token: str) -> None:
    _auth_cache.pop(token, None)


async def require_user(request: Request, session: SessionDep) -> UserInfo:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")
    now_mono = time.monotonic()
    cached = _auth_cache.get(token)
    if cached is not None:
        user_info, expires_epoch, checked_mono = cached
        if now_mono - checked_mono <= max(settings.auth_cache_ttl_seconds, 1) and expires_epoch > time.time():
            return user_info
        _auth_cache.pop(token, None)

    user_info = await get_session_user_info(session, token)
    if user_info is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    # Keep cache entry short-lived; DB is still source of truth.
    _auth_cache[token] = (user_info, time.time() + 30 * 24 * 3600, now_mono)
    return user_info


CurrentUser = Annotated[UserInfo, Depends(require_user)]
