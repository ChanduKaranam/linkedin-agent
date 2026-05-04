from __future__ import annotations

import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..logging_setup import get_logger
from ..storage import clear_linkedin_account, get_linkedin_account, upsert_linkedin_account

log = get_logger(__name__)

_LI_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
_LI_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
_LI_ME_URL = "https://api.linkedin.com/v2/userinfo"
_LI_POSTS_URL = "https://api.linkedin.com/rest/posts"
_LI_VERSION = "202503"
_TOKEN_TTL_SECONDS = 5_184_000  # 60 days


class LinkedInAuthError(ValueError):
    """Auth or token validity issue requiring re-connect."""


def _extract_member_name(me_data: dict) -> str | None:
    full_name = str(me_data.get("name", "")).strip()
    if full_name:
        return full_name
    given = str(me_data.get("given_name", "")).strip()
    family = str(me_data.get("family_name", "")).strip()
    joined = " ".join(x for x in [given, family] if x).strip()
    if joined:
        return joined
    localized_first = str(me_data.get("localizedFirstName", "")).strip()
    localized_last = str(me_data.get("localizedLastName", "")).strip()
    localized = " ".join(x for x in [localized_first, localized_last] if x).strip()
    return localized or None


def oauth_start(state: str | None = None) -> str:
    """Return the LinkedIn OAuth authorization URL."""
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "scope": "openid profile w_member_social",
    }
    if state:
        params["state"] = state
    return f"{_LI_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def oauth_callback(session: AsyncSession, code: str) -> dict:
    """Exchange authorization code for tokens, fetch member URN, persist."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            _LI_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.linkedin_redirect_uri,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

    access_token: str = token_data["access_token"]
    refresh_token: str | None = token_data.get("refresh_token")
    expires_in: int = token_data.get("expires_in", _TOKEN_TTL_SECONDS)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    async with httpx.AsyncClient(timeout=10) as client:
        me_resp = await client.get(
            _LI_ME_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        me_resp.raise_for_status()
        me_data = me_resp.json()

    member_id: str = me_data.get("sub", "")
    member_urn = f"urn:li:person:{member_id}"

    await upsert_linkedin_account(session, access_token, refresh_token, expires_at, member_urn)
    log.info("linkedin_oauth_connected", member_urn=member_urn)
    return {"member_urn": member_urn, "expires_at": expires_at.isoformat()}


async def get_connection_status(session: AsyncSession) -> dict:
    account = await get_linkedin_account(session)
    if account is None:
        return {"connected": False, "expires_at": None, "member_urn": None, "member_name": None}
    now = datetime.now(timezone.utc)
    connected = account["expires_at"] > now
    member_name: str | None = None
    if connected:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                me_resp = await client.get(
                    _LI_ME_URL,
                    headers={"Authorization": f"Bearer {account['access_token']}"},
                )
                if me_resp.status_code == 200:
                    member_name = _extract_member_name(me_resp.json())
        except Exception:
            member_name = None
    return {
        "connected": connected,
        "expires_at": account["expires_at"].isoformat(),
        "member_urn": account["member_urn"],
        "member_name": member_name,
    }


async def publish_post(session: AsyncSession, content: str) -> str:
    """POST the content to LinkedIn. Returns the post URN from the response header."""
    account = await get_linkedin_account(session)
    if account is None:
        raise LinkedInAuthError("LinkedIn account not connected. Authorize first.")

    now = datetime.now(timezone.utc)
    if account["expires_at"] <= now:
        raise LinkedInAuthError("LinkedIn access token has expired. Please reconnect.")

    payload = {
        "author": account["member_urn"],
        "commentary": content,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            _LI_POSTS_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {account['access_token']}",
                "LinkedIn-Version": _LI_VERSION,
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code == 401:
            # Token can be revoked before expires_at; clear persisted account so UI
            # immediately reflects disconnected state and prompts re-connect.
            await clear_linkedin_account(session)
            raise LinkedInAuthError("LinkedIn token rejected (401). Please reconnect.")
        resp.raise_for_status()
        post_urn = resp.headers.get("x-restli-id", "")

    log.info("linkedin_post_published", urn=post_urn, chars=len(content))
    return post_urn
