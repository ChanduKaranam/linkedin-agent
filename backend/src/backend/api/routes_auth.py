from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from ..auth_password import verify_password
from ..config import get_settings
from ..storage import create_session, delete_session, get_user_by_username
from .deps_auth import CurrentUser, SessionDep
from .schemas import LoginIn, MeOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(body: LoginIn, response: Response, session: SessionDep) -> MeOut:
    settings = get_settings()
    user = await get_user_by_username(session, body.username)
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = await create_session(session, user.username)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite=settings.session_cookie_samesite,
        secure=settings.session_cookie_secure,
        max_age=10 * 365 * 24 * 3600,
    )
    return MeOut(username=user.username)


@router.post("/logout")
async def logout(request: Request, response: Response, session: SessionDep) -> dict:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await delete_session(session, token)
    response.delete_cookie(key=settings.session_cookie_name)
    return {"ok": True}


@router.get("/me")
async def me(current_user: CurrentUser) -> MeOut:
    return MeOut(username=current_user.username)
