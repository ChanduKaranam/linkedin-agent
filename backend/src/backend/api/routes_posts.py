from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.post_writer import generate_blog_post, generate_linkedin_post
from ..db import get_session
from ..integrations import linkedin as li
from ..logging_setup import get_logger
from ..storage import (
    add_style_sample,
    create_generated_post,
    get_generated_post,
    get_linkedin_account,
    get_style_samples_for_few_shot,
    get_trend_by_slug,
    get_trends_for_run,
    list_chat_messages,
    list_generated_posts,
    list_insights,
    mark_post_published,
    update_generated_post_content,
)
from ..style.profile import get_profile_text, refresh_profile_if_stale
from .schemas import (
    GeneratedPostOut,
    GeneratedPostPatchIn,
    GeneratePostIn,
    LinkedInStatusOut,
    PublishResponseOut,
)

router = APIRouter()
log = get_logger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _date_parse(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")


def _post_to_out(p: dict) -> GeneratedPostOut:
    return GeneratedPostOut(**p)


async def _load_context(session: AsyncSession, trend, run_id: str, slug: str) -> tuple[list[dict], list[dict], str, list[str]]:
    """Fetch chat history, insights, style profile and samples for a trend."""
    chat_history = await list_chat_messages(session, run_id=run_id, slug=slug, limit=200)
    insights = await list_insights(session, run_id=run_id, slug=slug)
    style_profile = await get_profile_text(session)
    style_samples = await get_style_samples_for_few_shot(session, k=5)
    return chat_history, insights, style_profile, style_samples


# ── Daily trend posts ─────────────────────────────────────────────────────────

@router.get("/posts/{date}/{slug}", response_model=list[GeneratedPostOut])
async def list_posts_daily(date: str, slug: str, session: SessionDep) -> list[GeneratedPostOut]:
    run_date = _date_parse(date)
    posts = await list_generated_posts(session, run_date=run_date, slug=slug)
    return [_post_to_out(p) for p in posts]


@router.post("/posts/{date}/{slug}/linkedin", response_model=GeneratedPostOut, status_code=201)
async def generate_daily_linkedin(
    date: str, slug: str, session: SessionDep, bg: BackgroundTasks,
    body: GeneratePostIn = GeneratePostIn(),
) -> GeneratedPostOut:
    run_date = _date_parse(date)
    trend = await get_trend_by_slug(session, run_date, slug)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found.")

    chat_history, insights, style_profile, style_samples = await _load_context(
        session, trend, trend.run_id, slug
    )
    result = await generate_linkedin_post(
        trend, chat_history, insights, style_profile, style_samples,
        user_instructions=body.user_instructions,
    )
    post_id = await create_generated_post(
        session, "linkedin", trend.run_id, run_date, slug,
        result["content"], result["hashtags"],
    )
    bg.add_task(_bg_refresh_profile, trend.run_id)
    post = await get_generated_post(session, post_id)
    return _post_to_out(post)


@router.post("/posts/{date}/{slug}/blog", response_model=GeneratedPostOut, status_code=201)
async def generate_daily_blog(
    date: str, slug: str, session: SessionDep, bg: BackgroundTasks,
    body: GeneratePostIn = GeneratePostIn(),
) -> GeneratedPostOut:
    run_date = _date_parse(date)
    trend = await get_trend_by_slug(session, run_date, slug)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found.")

    chat_history, insights, style_profile, style_samples = await _load_context(
        session, trend, trend.run_id, slug
    )
    result = await generate_blog_post(
        trend, chat_history, insights, style_profile, style_samples,
        user_instructions=body.user_instructions,
    )
    content = f"# {result['title']}\n\n{result['content_markdown']}"
    post_id = await create_generated_post(
        session, "blog", trend.run_id, run_date, slug,
        content, result["tags"],
    )
    post = await get_generated_post(session, post_id)
    return _post_to_out(post)


# ── Ad-hoc/search run posts ────────────────────────────────────────────────────

@router.get("/posts/runs/{run_id}/{slug}", response_model=list[GeneratedPostOut])
async def list_posts_run(run_id: str, slug: str, session: SessionDep) -> list[GeneratedPostOut]:
    posts = await list_generated_posts(session, run_id=run_id, slug=slug)
    return [_post_to_out(p) for p in posts]


@router.post("/posts/runs/{run_id}/{slug}/linkedin", response_model=GeneratedPostOut, status_code=201)
async def generate_run_linkedin(
    run_id: str, slug: str, session: SessionDep, bg: BackgroundTasks,
    body: GeneratePostIn = GeneratePostIn(),
) -> GeneratedPostOut:
    trends = await get_trends_for_run(session, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found for this run.")

    chat_history, insights, style_profile, style_samples = await _load_context(
        session, trend, run_id, slug
    )
    result = await generate_linkedin_post(
        trend, chat_history, insights, style_profile, style_samples,
        user_instructions=body.user_instructions,
    )
    post_id = await create_generated_post(
        session, "linkedin", run_id, trend.run_date, slug,
        result["content"], result["hashtags"],
    )
    bg.add_task(_bg_refresh_profile, run_id)
    post = await get_generated_post(session, post_id)
    return _post_to_out(post)


@router.post("/posts/runs/{run_id}/{slug}/blog", response_model=GeneratedPostOut, status_code=201)
async def generate_run_blog(
    run_id: str, slug: str, session: SessionDep, bg: BackgroundTasks,
    body: GeneratePostIn = GeneratePostIn(),
) -> GeneratedPostOut:
    trends = await get_trends_for_run(session, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found for this run.")

    chat_history, insights, style_profile, style_samples = await _load_context(
        session, trend, run_id, slug
    )
    result = await generate_blog_post(
        trend, chat_history, insights, style_profile, style_samples,
        user_instructions=body.user_instructions,
    )
    content = f"# {result['title']}\n\n{result['content_markdown']}"
    post_id = await create_generated_post(
        session, "blog", run_id, trend.run_date, slug,
        content, result["tags"],
    )
    post = await get_generated_post(session, post_id)
    return _post_to_out(post)


# ── Shared post edit + publish ─────────────────────────────────────────────────

@router.patch("/posts/{post_id}", response_model=GeneratedPostOut)
async def patch_post(post_id: int, body: GeneratedPostPatchIn, session: SessionDep) -> GeneratedPostOut:
    post = await get_generated_post(session, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")
    await update_generated_post_content(session, post_id, body.content_markdown, body.tags)
    # User edits are high-quality style signal — record them
    await add_style_sample(session, "post_edit", body.content_markdown, source_ref=post_id)
    updated = await get_generated_post(session, post_id)
    return _post_to_out(updated)


@router.post("/posts/{post_id}/publish", response_model=PublishResponseOut)
async def publish_post_endpoint(post_id: int, session: SessionDep) -> PublishResponseOut:
    post = await get_generated_post(session, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")
    if post["kind"] != "linkedin":
        raise HTTPException(status_code=400, detail="Only LinkedIn posts can be published via this endpoint.")

    try:
        urn = await li.publish_post(session, post["content_markdown"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await mark_post_published(session, post_id, urn)
    return PublishResponseOut(post_urn=urn, status="published")


# ── LinkedIn OAuth admin ───────────────────────────────────────────────────────

@router.get("/admin/linkedin/status", response_model=LinkedInStatusOut)
async def linkedin_status(session: SessionDep) -> LinkedInStatusOut:
    status = await li.get_connection_status(session)
    return LinkedInStatusOut(**status)


@router.get("/admin/linkedin/authorize")
async def linkedin_authorize() -> RedirectResponse:
    from ..config import get_settings
    settings = get_settings()
    if not settings.linkedin_client_id:
        raise HTTPException(status_code=503, detail="LinkedIn OAuth not configured. Set LINKEDIN_CLIENT_ID in .env.")
    url = li.oauth_start()
    return RedirectResponse(url=url)


@router.get("/admin/linkedin/callback")
async def linkedin_callback(code: str, session: SessionDep) -> dict:
    try:
        result = await li.oauth_callback(session, code)
    except Exception as exc:
        log.error("linkedin_oauth_callback_failed", error=str(exc))
        raise HTTPException(status_code=400, detail=f"OAuth failed: {exc}")
    return {"connected": True, **result}


# ── Background helper ─────────────────────────────────────────────────────────

async def _bg_refresh_profile(run_id: str) -> None:
    from ..db import _get_factory
    try:
        async with _get_factory()() as session:
            await refresh_profile_if_stale(session)
    except Exception as exc:
        log.warning("bg_profile_refresh_failed", error=str(exc))
