from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session
from ..db_models import User
from ..storage import get_session_user

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_user(request: Request, session: SessionDep) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")
    user = await get_session_user(session, token)
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


CurrentUser = Annotated[User, Depends(require_user)]
