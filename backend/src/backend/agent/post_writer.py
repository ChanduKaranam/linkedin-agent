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


def _is_question(text: str) -> bool:
    stripped = text.strip()
    return stripped.endswith("?") or stripped.lower().startswith(("what ", "why ", "how ", "when ", "who ", "which ", "can ", "could ", "should ", "would ", "is ", "are ", "do ", "does "))


def _format_user_content(chat_messages: list[dict], insights: list[dict]) -> str:
    """
    Organise the user's own words into three buckets:
      1. Questions they asked (reveals curiosity / angles they care about)
      2. Opinions and statements (their actual take — use these verbatim in the post)
      3. Perspectives from saved insights

    Only user-authored text is included — assistant responses are excluded.
    """
    user_msgs = [m["content"].strip() for m in chat_messages if m["role"] == "user" and len(m["content"].strip()) >= 15]

    questions = [m for m in user_msgs if _is_question(m)]
    statements = [m for m in user_msgs if not _is_question(m)]

    parts: list[str] = []

    if questions:
        parts.append("### Questions this person asked (shows what they're curious about — let this shape the post's angle):")
        for q in questions[:10]:
            parts.append(f'  • "{q}"')

    if statements:
        parts.append("### Their opinions and observations (use these verbatim where possible — these ARE their voice):")
        for s in statements[:15]:
            parts.append(f'  • "{s}"')

    if insights:
        parts.append("### Explicit insights they saved (highest signal — these are deliberately noted perspectives):")
        for ins in insights[:20]:
            text = ins["user_perspective"].strip()
            if len(text) < 10:
                continue
            entry = f'  • "{text}"'
            # If the insight has a meaningful summary (not an auto-generated label), include it
            summary = (ins.get("summary") or "").strip()
            if summary and not summary.startswith("Edited ") and len(summary) > 20:
                entry += f'\n    → Context: "{summary[:200]}"'
            parts.append(entry)
        if ins.get("tags"):
            tag_str = ", ".join(ins["tags"][:5])
            parts[-1] += f"\n    Tags: {tag_str}"

    if not parts:
        return "(No chat messages or insights yet — write in the user's voice using the style profile and samples above.)"

    header = "IMPORTANT: The content below represents this specific person's thinking about this topic. Build the post around their perspective, not a generic summary.\n"
    return header + "\n\n".join(parts)


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
