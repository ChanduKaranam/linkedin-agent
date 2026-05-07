from __future__ import annotations

import httpx

from ..config import get_settings


class SlackError(RuntimeError):
    pass


def _auth_headers() -> dict[str, str]:
    token = get_settings().slack_bot_token.strip()
    if not token:
        raise SlackError("Slack bot token is not configured. Set SLACK_BOT_TOKEN in .env.")
    return {"Authorization": f"Bearer {token}"}


async def fetch_channel_messages(channel_id: str, limit: int = 40, since_ts: str | None = None) -> list[dict]:
    headers = _auth_headers()
    params: dict[str, str | int] = {"channel": channel_id, "limit": limit}
    if since_ts:
        params["oldest"] = since_ts
        params["inclusive"] = "false"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            "https://slack.com/api/conversations.history",
            params=params,
            headers=headers,
        )
    data = resp.json()
    if not data.get("ok"):
        raise SlackError(f"Slack history failed: {data.get('error', 'unknown_error')}")
    messages = data.get("messages", [])
    out: list[dict] = []
    for m in messages:
        text = str(m.get("text", "")).strip()
        if not text:
            continue
        out.append(
            {
                "user": str(m.get("user") or m.get("username") or "unknown"),
                "text": text,
                "ts": str(m.get("ts", "")),
            }
        )
    return out


async def post_message(channel_id: str, text: str) -> dict:
    headers = {**_auth_headers(), "Content-Type": "application/json; charset=utf-8"}
    payload = {"channel": channel_id, "text": text}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post("https://slack.com/api/chat.postMessage", json=payload, headers=headers)
    data = resp.json()
    if not data.get("ok"):
        raise SlackError(f"Slack post failed: {data.get('error', 'unknown_error')}")
    return {"ok": True, "channel": str(data.get("channel", "")), "ts": str(data.get("ts", ""))}
