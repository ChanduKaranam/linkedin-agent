from __future__ import annotations

import json
import uuid
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..logging_setup import get_logger
from ..models import Cluster, DailyBriefs, TrendSummary
from .prompts import (
    CLUSTER_INSTRUCTION,
    CLUSTER_USER_TEMPLATE,
    DAILY_SYNTHESIS_INSTRUCTION,
    DAILY_SYNTHESIS_USER_TEMPLATE,
    SUMMARIZE_INSTRUCTION,
    SUMMARIZE_USER_TEMPLATE,
    SYNTHESIS_INSTRUCTION,
    SYNTHESIS_USER_TEMPLATE,
)

log = get_logger(__name__)


def _make_model(model_str: str) -> LiteLlm:
    return LiteLlm(model=model_str)


def _build_cluster_agent(topic: str, model_str: str) -> LlmAgent:
    return LlmAgent(
        name="cluster_agent",
        model=_make_model(model_str),
        instruction=CLUSTER_INSTRUCTION.format(topic=topic),
        output_schema=list[Cluster],
        output_key="clusters",
    )


def _build_summarize_agent(topic: str, model_str: str) -> LlmAgent:
    return LlmAgent(
        name="summarize_agent",
        model=_make_model(model_str),
        instruction=SUMMARIZE_INSTRUCTION.format(topic=topic),
        output_schema=TrendSummary,
        output_key="summary",
    )


async def _run_agent(agent: LlmAgent, user_prompt: str) -> Any:
    """Run an ADK agent for a single turn, return the validated output_schema object."""
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="trend_agent",
        user_id="pipeline",
        session_id=str(uuid.uuid4()),
    )
    runner = Runner(
        agent=agent,
        app_name="trend_agent",
        session_service=session_service,
    )

    final_text: str | None = None
    async for event in runner.run_async(
        user_id="pipeline",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=user_prompt)],
        ),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text
            break

    if final_text is None:
        raise RuntimeError("ADK agent produced no final response")

    # Strip markdown code fences Mistral sometimes wraps output in
    clean = _strip_fences(final_text)

    # Parse and validate via the output schema
    schema = agent.output_schema
    if hasattr(schema, "__origin__"):
        # list[Cluster]
        raw = json.loads(clean)
        inner = schema.__args__[0]
        return [inner.model_validate(item) for item in raw]
    return schema.model_validate_json(clean)


def _strip_fences(text: str) -> str:
    """Strip markdown code fences that LLMs sometimes wrap JSON output in."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        # Drop opening fence line (```json or ```)
        lines = lines[1:]
        # Drop closing fence line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


async def cluster_articles(
    snippets: list[dict],
    topic: str,
    model_str: str,
) -> list[Cluster]:
    snippets_text = "\n".join(
        f"[{i}] {s['title']} ({s['domain']}): {s['snippet']}"
        for i, s in enumerate(snippets)
    )
    prompt = CLUSTER_USER_TEMPLATE.format(count=len(snippets), snippets=snippets_text)
    agent = _build_cluster_agent(topic, model_str)
    try:
        result = await _run_agent(agent, prompt)
        log.info("cluster_complete", cluster_count=len(result))
        return result
    except Exception as exc:
        log.error("cluster_agent_failed", error=str(exc))
        raise


async def summarize_cluster(
    trend_id: str,
    content_parts: list[str],
    topic: str,
    model_str: str,
) -> TrendSummary:
    combined = "\n\n---\n\n".join(content_parts)
    prompt = SUMMARIZE_USER_TEMPLATE.format(trend_id=trend_id, content=combined)
    agent = _build_summarize_agent(topic, model_str)
    try:
        result = await _run_agent(agent, prompt)
        log.info("summarize_complete", trend_id=trend_id, headline=result.headline)
        return result
    except Exception as exc:
        log.error("summarize_agent_failed", trend_id=trend_id, error=str(exc))
        raise


async def synthesize_daily(
    content_parts: list[str],
    topic: str,
    model_str: str,
    run_date: "date | None" = None,
) -> DailyBriefs:
    """Daily pipeline: read all articles, identify distinct stories, return one brief per story.
    Replaces cluster + per-cluster summarize — no more 10 headlines for the same event."""
    from datetime import date as _date, timedelta
    today = run_date or _date.today()
    cutoff = (today - timedelta(days=1)).isoformat()
    today_str = today.isoformat()

    combined = "\n\n---\n\n".join(content_parts)
    prompt = DAILY_SYNTHESIS_USER_TEMPLATE.format(
        topic=topic, content=combined, today=today_str, cutoff=cutoff
    )
    agent = LlmAgent(
        name="daily_synthesis_agent",
        model=_make_model(model_str),
        instruction=DAILY_SYNTHESIS_INSTRUCTION.format(
            topic=topic, today=today_str, cutoff=cutoff
        ),
        output_schema=DailyBriefs,
        output_key="daily_briefs",
    )
    try:
        result = await _run_agent(agent, prompt)
        log.info("daily_synthesis_complete", topic=topic, story_count=len(result.trends))
        return result
    except Exception as exc:
        log.error("daily_synthesis_failed", topic=topic, error=str(exc))
        raise


async def synthesize_all(
    content_parts: list[str],
    topic: str,
    model_str: str,
) -> TrendSummary:
    """Send all scraped content in one LLM call and return a single comprehensive TrendSummary.
    Used by the search pipeline — no clustering step."""
    combined = "\n\n---\n\n".join(content_parts)
    prompt = SYNTHESIS_USER_TEMPLATE.format(topic=topic, content=combined)
    agent = LlmAgent(
        name="synthesis_agent",
        model=_make_model(model_str),
        instruction=SYNTHESIS_INSTRUCTION.format(topic=topic),
        output_schema=TrendSummary,
        output_key="synthesis",
    )
    try:
        result = await _run_agent(agent, prompt)
        log.info("synthesis_complete", topic=topic, headline=result.headline)
        return result
    except Exception as exc:
        log.error("synthesis_agent_failed", topic=topic, error=str(exc))
        raise
