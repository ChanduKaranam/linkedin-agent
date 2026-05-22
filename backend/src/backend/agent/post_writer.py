from __future__ import annotations

import json
from pathlib import Path

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

SKILLS_DIR = Path(__file__).parents[4] / "skills"


def _load_skill_file(filename: str) -> str:
    path = SKILLS_DIR / filename
    if not path.exists():
        log.warning("skill_file_not_found", path=str(path))
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        log.error("skill_file_read_error", filename=filename, error=str(e))
        return ""


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
            summary = (ins.get("summary") or "").strip()
            if summary and not summary.startswith("Edited ") and len(summary) > 20:
                entry += f'\n    → Context: "{summary[:200]}"'
            if ins.get("tags"):
                tag_str = ", ".join(ins["tags"][:5])
                entry += f"\n    Tags: {tag_str}"
            parts.append(entry)

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
    style: str = "leadership",
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

    system_prompt = LINKEDIN_POST_SYSTEM
    
    # Load dynamic LinkedIn Generator Skill
    linkedin_gen = _load_skill_file("06_tilicho_linkedin_post_generator.md")
    if linkedin_gen:
        system_prompt += f"\n\n## Dynamic Generator Framework Guidelines\n{linkedin_gen}"
        
    # Load dynamic LinkedIn Evaluator Skill based on Style
    eval_file = (
        "05_tilicho_leadership_linkedin_evaluator.md"
        if style == "leadership"
        else "04_tilicho_technical_linkedin_evaluator.md"
    )
    eval_skill = _load_skill_file(eval_file)
    if eval_skill:
        system_prompt += f"\n\n## Evaluation Criteria to Score Highly Against\n{eval_skill}"

    response = await litellm.acompletion(
        model=cfg.models.summarize,
        messages=[
            {"role": "system", "content": system_prompt},
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

    log.info("linkedin_post_generated", chars=len(content), hashtags=len(hashtags), style=style)
    return {"content": content, "hashtags": hashtags}


async def generate_blog_post(
    trend: PersistedTrend,
    chat_messages: list[dict],
    insights: list[dict],
    style_profile: str,
    style_samples: list[str],
    *,
    style: str = "leadership",
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

    system_prompt = BLOG_POST_SYSTEM
    
    # Load dynamic Blog Generator & Evaluator Skills based on Style
    blog_gen = ""
    if style == "leadership":
        blog_gen = _load_skill_file("03_tilicho_leadership_blog_generator.md")
        eval_file = "02_tilicho_leadership_blog_evaluator.md"
    else:
        # Technical style
        eval_file = "01_tilicho_technical_blog_evaluator.md"
        blog_gen = (
            "## Technical Generation Guidelines\n"
            "Generate practitioner-focused technical content. Prioritize implementation maturity, "
            "engineering credibility, operational realism, systems thinking, and proof-of-work. "
            "Ensure technical examples or concepts are clear, accurate, and structured for engineering leaders."
        )

    eval_skill = _load_skill_file(eval_file)
    
    if blog_gen:
        system_prompt += f"\n\n{blog_gen}"
    if eval_skill:
        system_prompt += f"\n\n## Evaluation Criteria to Score Highly Against\n{eval_skill}"

    response = await litellm.acompletion(
        model=cfg.models.summarize,
        messages=[
            {"role": "system", "content": system_prompt},
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

    log.info("blog_post_generated", chars=len(content_markdown), tags=len(tags), style=style)
    return {"title": title, "content_markdown": content_markdown, "tags": tags}


async def evaluate_post_draft(
    content: str,
    kind: str,
    style: str,
    trend_headline: str,
    trend_summary: str,
) -> dict:
    """Evaluate a generated post draft against the corresponding evaluator skill.

    Returns a dict with keys: score, strengths, critique, suggestions.
    """
    cfg = get_topic_config()

    # Resolve correct evaluator file name
    if kind == "blog":
        eval_file = (
            "02_tilicho_leadership_blog_evaluator.md"
            if style == "leadership"
            else "01_tilicho_technical_blog_evaluator.md"
        )
    else:  # linkedin
        eval_file = (
            "05_tilicho_leadership_linkedin_evaluator.md"
            if style == "leadership"
            else "04_tilicho_technical_linkedin_evaluator.md"
        )

    evaluator_criteria = _load_skill_file(eval_file)
    if not evaluator_criteria:
        log.warning("evaluator_criteria_empty", eval_file=eval_file)
        evaluator_criteria = "Evaluate draft for professional quality, readability, and topic relevance."

    system_msg = """You are an elite peer reviewer and editor. Your task is to evaluate the provided draft against specific style evaluation skill guidelines.

You MUST evaluate the draft objectively and strictly. Provide constructive critique, identify concrete strengths, and give actionable suggestions.

You must return ONLY a valid JSON object matching this schema (do not include markdown fences, prose, or extra text):
{
  "score": 8.5,  # float between 0.0 and 10.0
  "strengths": ["list of specific strengths"],
  "critique": ["list of specific critiques/areas for improvement"],
  "suggestions": ["list of actionable suggestions to refine and improve the post"]
}
"""

    user_msg = f"""## Draft to Evaluate
{content}

## Target Topic Context
Headline: {trend_headline}
Summary: {trend_summary}

## Evaluation Criteria (Skill Guidelines)
{evaluator_criteria}

Please evaluate the draft against the criteria and topic context, and return the structured JSON evaluation.
"""

    try:
        response = await litellm.acompletion(
            model=cfg.models.summarize,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
        )
        raw = (response.choices[0].message.content or "").strip()
        data = json.loads(_strip_fences(raw))
        # Ensure correct keys and types
        score = float(data.get("score", 7.0))
        strengths = [str(x) for x in data.get("strengths", [])]
        critique = [str(x) for x in data.get("critique", [])]
        suggestions = [str(x) for x in data.get("suggestions", [])]

        # Clamp score between 0 and 10
        score = max(0.0, min(10.0, score))

        return {
            "score": round(score, 1),
            "strengths": strengths,
            "critique": critique,
            "suggestions": suggestions,
        }
    except Exception as e:
        log.error("evaluate_draft_failed", error=str(e))
        return {
            "score": 5.0,
            "strengths": [],
            "critique": [f"Evaluation failed: {e}"],
            "suggestions": ["Try editing the draft to trigger re-evaluation."],
        }
