from __future__ import annotations

import json

import litellm

from ..config import get_topic_config
from ..logging_setup import get_logger
from ..models import PersistedTrend
from .prompts import (
    BLOG_POST_SYSTEM,
    BLOG_POST_USER,
    LINKEDIN_POST_SYSTEM,
    LINKEDIN_POST_USER,
)

log = get_logger(__name__)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _format_key_points(key_points: list[str]) -> str:
    return "\n".join(f"- {p}" for p in key_points)


def _format_user_content(chat_messages: list[dict], insights: list[dict]) -> str:
    parts: list[str] = []
    user_msgs = [m for m in chat_messages if m["role"] == "user"]
    if user_msgs:
        parts.append("### Chat messages (user's own words):")
        for m in user_msgs:
            parts.append(f'"{m["content"]}"')
    if insights:
        parts.append("### Saved insights (user's explicit perspectives):")
        for ins in insights:
            parts.append(f'"{ins["user_perspective"]}"')
    return "\n\n".join(parts) if parts else "(No user insights or chat messages yet.)"


async def generate_linkedin_post(
    trend: PersistedTrend,
    chat_messages: list[dict],
    insights: list[dict],
    style_profile: str,
    style_samples: list[str],
    *,
    user_instructions: str = "",
) -> dict:
    """Generate a LinkedIn post draft. Returns {content: str, hashtags: list[str]}."""
    cfg = get_topic_config()

    samples_text = (
        "\n\n---\n\n".join(style_samples)
        if style_samples
        else "(No writing samples collected yet — write in a clear professional voice.)"
    )
    profile_text = style_profile or "(No style profile yet — write in a clear professional voice.)"

    user_msg = LINKEDIN_POST_USER.format(
        headline=trend.headline,
        one_liner=trend.one_liner,
        key_points=_format_key_points(trend.key_points),
        style_profile=profile_text,
        style_samples=samples_text,
        user_insights=_format_user_content(chat_messages, insights),
    )
    if user_instructions.strip():
        user_msg += f"\n\n## Specific instructions for this version\n{user_instructions.strip()}"

    response = await litellm.acompletion(
        model=cfg.models.summarize,
        messages=[
            {"role": "system", "content": LINKEDIN_POST_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    try:
        data = json.loads(_strip_fences(raw))
        content = str(data.get("content", raw))
        hashtags = [str(t).lstrip("#") for t in data.get("hashtags", [])]
    except (json.JSONDecodeError, KeyError):
        content = raw
        hashtags = []

    log.info("linkedin_post_generated", chars=len(content), hashtags=len(hashtags))
    return {"content": content, "hashtags": hashtags}


async def generate_blog_post(
    trend: PersistedTrend,
    chat_messages: list[dict],
    insights: list[dict],
    style_profile: str,
    style_samples: list[str],
    *,
    user_instructions: str = "",
) -> dict:
    """Generate a blog post draft. Returns {title: str, content_markdown: str, tags: list[str]}."""
    cfg = get_topic_config()

    samples_text = (
        "\n\n---\n\n".join(style_samples)
        if style_samples
        else "(No writing samples collected yet — write in a clear professional voice.)"
    )
    profile_text = style_profile or "(No style profile yet — write in a clear professional voice.)"

    user_msg = BLOG_POST_USER.format(
        headline=trend.headline,
        one_liner=trend.one_liner,
        key_points=_format_key_points(trend.key_points),
        detailed_markdown=trend.detailed_markdown,
        style_profile=profile_text,
        style_samples=samples_text,
        user_insights=_format_user_content(chat_messages, insights),
    )
    if user_instructions.strip():
        user_msg += f"\n\n## Specific instructions for this version\n{user_instructions.strip()}"

    response = await litellm.acompletion(
        model=cfg.models.summarize,
        messages=[
            {"role": "system", "content": BLOG_POST_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    try:
        data = json.loads(_strip_fences(raw))
        title = str(data.get("title", trend.headline))
        content_markdown = str(data.get("content_markdown", raw))
        tags = [str(t) for t in data.get("tags", [])]
    except (json.JSONDecodeError, KeyError):
        title = trend.headline
        content_markdown = raw
        tags = []

    log.info("blog_post_generated", chars=len(content_markdown), tags=len(tags))
    return {"title": title, "content_markdown": content_markdown, "tags": tags}
