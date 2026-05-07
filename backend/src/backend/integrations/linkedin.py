from __future__ import annotations

import base64
import json
import urllib.parse
import unicodedata
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
_LI_IMAGES_URL = "https://api.linkedin.com/rest/images"
_LI_VERSION = "202503"
_TOKEN_TTL_SECONDS = 5_184_000  # 60 days
_LI_COMMENTARY_LIMIT = 3000  # LinkedIn REST API hard limit for commentary field


class LinkedInAuthError(ValueError):
    """Auth or token validity issue requiring re-connect."""


def _to_linkedin_safe_commentary(content: str) -> str:
    """Convert text to a parser-safe LinkedIn commentary representation."""
    text = unicodedata.normalize("NFKC", content)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")

    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201C": '"',
        "\u201D": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "\u00A0": " ",  # non-breaking space
        "\u200B": "",   # zero-width space
        "\u200C": "",   # zero-width non-joiner
        "\u200D": "",   # zero-width joiner
        "\uFEFF": "",   # zero-width no-break space
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Keep commentary as plain text to avoid any parser quirks in rendered feeds.
    text = (
        text.replace("(", "")
        .replace(")", "")
        .replace("*", "")
        .replace("_", "")
        .replace("`", "")
    )

    return text.strip()


def _duplicate_retry_commentary(content: str) -> str:
    suffix = f"\n\n(Update: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})"
    max_base_len = _LI_COMMENTARY_LIMIT - len(suffix)
    base = content[:max_base_len].rstrip() if len(content) + len(suffix) > _LI_COMMENTARY_LIMIT else content
    return f"{base}{suffix}"


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
    member_name = _extract_member_name(me_data)

    await upsert_linkedin_account(session, access_token, refresh_token, expires_at, member_urn, member_name)
    log.info("linkedin_oauth_connected", member_urn=member_urn, member_name=member_name)
    return {"member_urn": member_urn, "member_name": member_name, "expires_at": expires_at.isoformat()}


async def get_connection_status(session: AsyncSession) -> dict:
    account = await get_linkedin_account(session)
    if account is None:
        return {"connected": False, "expires_at": None, "member_urn": None, "member_name": None}
    now = datetime.now(timezone.utc)
    connected = account["expires_at"] > now
    # Use the name stored during OAuth as primary source. Only attempt a live fetch
    # if the stored name is missing (e.g., account connected before this field was added).
    member_name: str | None = account.get("member_name")
    if connected and not member_name:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                me_resp = await client.get(
                    _LI_ME_URL,
                    headers={"Authorization": f"Bearer {account['access_token']}"},
                )
                log.info("linkedin_userinfo_fetch", status=me_resp.status_code)
                if me_resp.status_code == 200:
                    me_data = me_resp.json()
                    log.info("linkedin_userinfo_fields", fields=list(me_data.keys()))
                    fetched_name = _extract_member_name(me_data)
                    if fetched_name:
                        member_name = fetched_name
                        # Persist so future calls don't need the live fetch
                        await upsert_linkedin_account(
                            session,
                            account["access_token"],
                            account.get("refresh_token"),
                            account["expires_at"],
                            account["member_urn"],
                            fetched_name,
                        )
                    else:
                        log.warning("linkedin_userinfo_no_name", fields=list(me_data.keys()), data=me_data)
                else:
                    log.warning("linkedin_userinfo_failed", status=me_resp.status_code, body=me_resp.text[:200])
        except Exception as exc:
            log.warning("linkedin_userinfo_exception", error=str(exc))
    return {
        "connected": connected,
        "expires_at": account["expires_at"].isoformat(),
        "member_urn": account["member_urn"],
        "member_name": member_name,
    }


def _parse_data_url(image_data_url: str) -> tuple[bytes, str]:
    if not image_data_url.startswith("data:") or ";base64," not in image_data_url:
        raise ValueError("Invalid image payload. Please select the image again.")
    header, encoded = image_data_url.split(";base64,", 1)
    content_type = header[5:].strip().lower()
    if content_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
        raise ValueError("Unsupported image type. Use PNG, JPEG, GIF, or WEBP.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("Invalid image encoding.") from exc
    if not data:
        raise ValueError("Image is empty.")
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Image is too large. Maximum size is 10 MB.")
    return data, content_type


async def _upload_linkedin_image(access_token: str, owner_urn: str, image_data_url: str) -> str:
    image_bytes, content_type = _parse_data_url(image_data_url)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": _LI_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    async with httpx.AsyncClient(timeout=40) as client:
        init_resp = await client.post(
            f"{_LI_IMAGES_URL}?action=initializeUpload",
            json={"initializeUploadRequest": {"owner": owner_urn}},
            headers={**headers, "Content-Type": "application/json"},
        )
        if init_resp.status_code == 401:
            raise LinkedInAuthError("LinkedIn token rejected (401). Please reconnect.")
        init_resp.raise_for_status()
        init_data = init_resp.json()
        upload_url = (
            init_data.get("value", {}).get("uploadUrl")
            or init_data.get("uploadUrl")
            or ""
        )
        image_urn = (
            init_data.get("value", {}).get("image")
            or init_data.get("image")
            or ""
        )
        if not upload_url or not image_urn:
            raise ValueError("LinkedIn image upload initialization failed.")

        upload_resp = await client.put(
            upload_url,
            content=image_bytes,
            headers={"Content-Type": content_type},
        )
        upload_resp.raise_for_status()
    return image_urn


async def publish_post(
    session: AsyncSession,
    content: str,
    image_data_url: str | None = None,
    image_alt_text: str = "",
) -> str:
    """POST the content to LinkedIn. Returns the post URN from the response header."""
    content = _to_linkedin_safe_commentary(content)

    account = await get_linkedin_account(session)
    if account is None:
        raise LinkedInAuthError("LinkedIn account not connected. Authorize first.")

    now = datetime.now(timezone.utc)
    if account["expires_at"] <= now:
        raise LinkedInAuthError("LinkedIn access token has expired. Please reconnect.")

    if len(content) > _LI_COMMENTARY_LIMIT:
        raise ValueError(
            f"Post is too long for LinkedIn ({len(content):,} chars). "
            f"LinkedIn allows a maximum of {_LI_COMMENTARY_LIMIT:,} characters. "
            "Please shorten the post in the editor and save before publishing."
        )

    image_urn: str | None = None
    if image_data_url:
        image_urn = await _upload_linkedin_image(
            account["access_token"], account["member_urn"], image_data_url
        )

    def _build_payload(commentary: str) -> dict:
        payload = {
            "author": account["member_urn"],
            "commentary": commentary,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if image_urn:
            payload["content"] = {
                "media": {
                    "id": image_urn,
                    **({"altText": image_alt_text.strip()} if image_alt_text.strip() else {}),
                }
            }
        return payload

    async with httpx.AsyncClient(timeout=20) as client:
        commentary_to_send = content
        for attempt in range(2):
            body_bytes = json.dumps(_build_payload(commentary_to_send), ensure_ascii=False).encode("utf-8")
            log.info(
                "linkedin_post_sending",
                chars=len(commentary_to_send),
                body_bytes=len(body_bytes),
                preview_start=commentary_to_send[:120].replace("\n", "↵"),
                preview_end=commentary_to_send[-80:].replace("\n", "↵"),
                duplicate_retry=(attempt == 1),
            )
            resp = await client.post(
                _LI_POSTS_URL,
                content=body_bytes,
                headers={
                    "Authorization": f"Bearer {account['access_token']}",
                    "LinkedIn-Version": _LI_VERSION,
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Content-Type": "application/json; charset=utf-8",
                },
            )
            if resp.status_code == 422 and "DUPLICATE_POST" in resp.text and attempt == 0:
                commentary_to_send = _duplicate_retry_commentary(content)
                continue
            break

        if resp.status_code == 401:
            # Token can be revoked before expires_at; clear persisted account so UI
            # immediately reflects disconnected state and prompts re-connect.
            await clear_linkedin_account(session)
            raise LinkedInAuthError("LinkedIn token rejected (401). Please reconnect.")
        if resp.status_code == 422 and "DUPLICATE_POST" in resp.text:
            raise ValueError(
                "LinkedIn rejected this as a duplicate post. "
                "Edit the text slightly (e.g., change one sentence, add/remove a hashtag, "
                "or wait before reposting) and publish again."
            )
        if not resp.is_success:
            log.error(
                "linkedin_post_failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
        resp.raise_for_status()
        post_urn = resp.headers.get("x-restli-id", "")

    log.info("linkedin_post_published", urn=post_urn, chars=len(content))
    return post_urn


async def delete_linkedin_post(session: AsyncSession, post_urn: str) -> None:
    """Delete a published post from LinkedIn. Raises LinkedInAuthError on auth failure."""
    account = await get_linkedin_account(session)
    if account is None:
        raise LinkedInAuthError("LinkedIn account not connected.")

    now = datetime.now(timezone.utc)
    if account["expires_at"] <= now:
        raise LinkedInAuthError("LinkedIn access token has expired.")

    encoded_urn = urllib.parse.quote(post_urn, safe="")
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.delete(
            f"{_LI_POSTS_URL}/{encoded_urn}",
            headers={
                "Authorization": f"Bearer {account['access_token']}",
                "LinkedIn-Version": _LI_VERSION,
                "X-Restli-Protocol-Version": "2.0.0",
            },
        )
        if resp.status_code == 401:
            await clear_linkedin_account(session)
            raise LinkedInAuthError("LinkedIn token rejected (401). Please reconnect.")
        if resp.status_code == 404:
            # Post not found on LinkedIn — it may have been deleted manually; treat as success
            log.warning("linkedin_post_not_found_on_delete", urn=post_urn)
            return
        resp.raise_for_status()

    log.info("linkedin_post_deleted", urn=post_urn)
