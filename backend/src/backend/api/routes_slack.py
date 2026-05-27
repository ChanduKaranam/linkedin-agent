from __future__ import annotations

import json
from datetime import datetime, timezone

import litellm
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session
from ..integrations import linkedin as li
from ..integrations.linkedin import LinkedInAuthError
from ..integrations.slack import SlackError, fetch_channel_messages, post_message
from .deps_auth import CurrentUser, require_user
from .schemas import (
    SlackChatIn,
    SlackChatOut,
    SlackGenerateIn,
    SlackGeneratedPostOut,
    SlackHistoryOut,
    SlackPublishLinkedInIn,
    SlackPublishLinkedInOut,
    SlackSendIn,
    SlackSendOut,
)

router = APIRouter()


def _resolve_channel(channel_id: str) -> str:
    if channel_id and channel_id.strip() and channel_id.strip().lower() != "default":
        return channel_id.strip()
    configured = get_settings().slack_default_channel_id.strip()
    if not configured:
        raise HTTPException(status_code=400, detail="Slack default channel is not configured.")
    return configured


def _format_history(messages: list[dict], limit: int) -> str:
    rows: list[str] = []
    for m in messages[:limit]:
        rows.append(f"- [{m.get('ts','')}] {m.get('user','unknown')}: {m.get('text','')}")
    return "\n".join(rows) if rows else "(no messages)"


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _extract_post_text(raw: str) -> tuple[str, list[str]]:
    """
    Accept multiple JSON shapes from the model and always return plain post text.
    Falls back to raw text when parsing fails.
    """
    cleaned = _strip_fences(raw)
    tags: list[str] = []
    try:
        parsed = json.loads(cleaned)
    except Exception:
        return raw.strip(), tags

    if isinstance(parsed, dict):
        candidates = [
            parsed.get("content_markdown"),
            parsed.get("content"),
            parsed.get("post"),
            parsed.get("linkedin_post"),
            parsed.get("text"),
            parsed.get("body"),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                text = candidate.strip()
                maybe_tags = parsed.get("tags", [])
                if isinstance(maybe_tags, list):
                    tags = [str(t) for t in maybe_tags]
                return text, tags

    return raw.strip(), tags


@router.get("/slack/channels/{channel_id}/messages", response_model=SlackHistoryOut)
async def get_slack_messages(
    channel_id: str,
    limit: int = Query(default=40, ge=1, le=120),
    since_ts: str | None = Query(default=None),
) -> SlackHistoryOut:
    resolved = _resolve_channel(channel_id)
    try:
        msgs = await fetch_channel_messages(resolved, limit=limit, since_ts=since_ts)
        return SlackHistoryOut(channel=resolved, messages=msgs)
    except SlackError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/slack/chat", response_model=SlackChatOut)
async def slack_chat(body: SlackChatIn) -> SlackChatOut:
    channel = _resolve_channel(body.channel_id)
    try:
        messages = await fetch_channel_messages(channel, limit=body.message_limit)
    except SlackError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    selected = body.selected_message.strip() or "(no selected message)"
    prompt = (
        "You are a concise assistant helping analyze Slack conversation context.\n"
        "Answer the user question grounded in the selected message and recent channel messages.\n\n"
        f"Selected message:\n{selected}\n\n"
        f"Recent channel messages:\n{_format_history(messages, body.message_limit)}\n\n"
        f"User question:\n{body.content.strip()}"
    )
    model = body.model.strip() or get_settings().mistral_api_key and "mistral/mistral-large-latest" or "mistral/mistral-small-latest"
    try:
        res = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}")
    reply = (res.choices[0].message.content or "").strip()
    return SlackChatOut(reply=reply or "I could not generate a response.")


async def _generate_post(kind: str, body: SlackGenerateIn) -> SlackGeneratedPostOut:
    channel = _resolve_channel(body.channel_id)
    try:
        messages = await fetch_channel_messages(channel, limit=body.message_limit)
    except SlackError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    selected = body.selected_message.strip()
    instructions = body.user_instructions.strip()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if kind == "linkedin":
        style = (
            "Write a professional LinkedIn post in markdown. Keep it punchy and structured.\n"
            "Return JSON with keys: content_markdown (string), tags (string[])."
        )
    else:
        style = (
            "Write a concise blog post draft in markdown with title and sections.\n"
            "Return JSON with keys: content_markdown (string), tags (string[])."
        )
    prompt = (
        f"{style}\n\nDate: {now}\n"
        f"Selected message:\n{selected or '(none)'}\n\n"
        f"Recent channel messages:\n{_format_history(messages, body.message_limit)}\n\n"
        f"User instructions:\n{instructions or '(none)'}"
    )
    try:
        res = await litellm.acompletion(
            model="mistral/mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}")
    raw = (res.choices[0].message.content or "").strip()
    content, tags = _extract_post_text(raw)
    return SlackGeneratedPostOut(kind=kind, content_markdown=content, tags=tags)


@router.post("/slack/generate/linkedin", response_model=SlackGeneratedPostOut)
async def slack_generate_linkedin(body: SlackGenerateIn) -> SlackGeneratedPostOut:
    return await _generate_post("linkedin", body)


@router.post("/slack/generate/blog", response_model=SlackGeneratedPostOut)
async def slack_generate_blog(body: SlackGenerateIn) -> SlackGeneratedPostOut:
    return await _generate_post("blog", body)


@router.post("/slack/post", response_model=SlackSendOut)
async def slack_post(body: SlackSendIn) -> SlackSendOut:
    channel = _resolve_channel(body.channel_id)
    try:
        out = await post_message(channel, body.text)
        return SlackSendOut(**out)
    except SlackError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/slack/publish/linkedin", response_model=SlackPublishLinkedInOut)
async def slack_publish_linkedin(body: SlackPublishLinkedInIn, current_user: CurrentUser, session: AsyncSession = Depends(get_session)) -> SlackPublishLinkedInOut:
    publish_text, _ = _extract_post_text(body.content)
    try:
        urn = await li.publish_post(session, current_user.user_id, publish_text)
    except LinkedInAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SlackPublishLinkedInOut(post_urn=urn, status="published")
