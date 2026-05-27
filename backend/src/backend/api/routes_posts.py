from __future__ import annotations

import secrets
import time
from datetime import date
from urllib.parse import quote
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.post_writer import generate_blog_post, generate_linkedin_post, evaluate_post_draft
from ..db import get_session
from ..integrations import linkedin as li
from ..integrations.linkedin import LinkedInAuthError
from ..logging_setup import get_logger
from ..storage import (
    add_style_sample,
    create_generated_post,
    delete_generated_post,
    get_generated_post,
    get_linkedin_account,
    get_style_samples_for_few_shot,
    get_trend_by_slug,
    get_trends_for_run,
    list_all_generated_posts,
    list_chat_messages,
    list_chat_messages_by_slug,
    list_generated_posts,
    list_insights,
    list_insights_by_slug,
    mark_post_published,
    update_generated_post_content,
)
from ..style.profile import get_profile_text, refresh_profile_if_stale
from .deps_auth import CurrentUser
from .schemas import (
    DeletePostOut,
    GeneratedPostListItem,
    GeneratedPostOut,
    GeneratedPostPatchIn,
    GeneratePostIn,
    LinkedInStatusOut,
    PublishPostIn,
    PublishResponseOut,
)

router = APIRouter()
log = get_logger(__name__)

# OAuth state nonce store: {nonce: (return_to, expires_ts)}
_oauth_state: dict[str, tuple[str, float]] = {}
_OAUTH_STATE_TTL = 600  # 10 minutes

# LinkedIn status cache: (value, expires_at) — refreshed on connect/disconnect
_li_status_cache: tuple[Any, float] | None = None
_LI_STATUS_TTL = 30.0


def _new_oauth_nonce(return_to: str) -> str:
    # Evict expired entries
    now = time.monotonic()
    expired = [k for k, (_, ts) in _oauth_state.items() if ts < now]
    for k in expired:
        del _oauth_state[k]
    nonce = secrets.token_urlsafe(32)
    _oauth_state[nonce] = (return_to, now + _OAUTH_STATE_TTL)
    return nonce


def _consume_oauth_nonce(nonce: str) -> str | None:
    entry = _oauth_state.pop(nonce, None)
    if entry is None:
        return None
    return_to, expires_ts = entry
    if time.monotonic() > expires_ts:
        return None
    return return_to

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _date_parse(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")


def _post_to_out(p: dict) -> GeneratedPostOut:
    return GeneratedPostOut(**p)


async def _load_context(session: AsyncSession, user_id: int, trend, run_id: str, slug: str) -> tuple[list[dict], list[dict], str, list[str]]:
    """Fetch full context for post generation for a specific user.

    - Chat messages and insights across ALL runs for this slug (only for this user).
    - Style profile is read as-is (refresh runs as a background task after generation
      so it doesn't add an extra LLM call to the hot path and cause timeouts).
    - 15 style samples for a richer voice model.
    """
    chat_history = await list_chat_messages_by_slug(session, user_id, slug, limit=400)
    insights = await list_insights_by_slug(session, user_id, slug, limit=200)
    style_profile = await get_profile_text(session, user_id)
    style_samples = await get_style_samples_for_few_shot(session, user_id, k=15)
    return chat_history, insights, style_profile, style_samples


# ── List all posts (library view) — must be registered before parameterized routes ──

@router.get("/posts/all", response_model=list[GeneratedPostListItem])
async def list_posts_all(kind: str, session: SessionDep, current_user: CurrentUser, limit: int = 100) -> list[GeneratedPostListItem]:
    if kind not in {"linkedin", "blog"}:
        raise HTTPException(status_code=400, detail="kind must be 'linkedin' or 'blog'.")
    effective_limit = min(limit, 200)
    try:
        rows = await list_all_generated_posts(session, current_user.user_id, kind=kind, limit=effective_limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    log.info("posts_library_listed", kind=kind, limit=effective_limit, count=len(rows))
    return [GeneratedPostListItem(**r) for r in rows]


@router.get("/posts/by-id/{post_id}", response_model=GeneratedPostOut)
async def get_post_by_id(post_id: int, session: SessionDep, current_user: CurrentUser) -> GeneratedPostOut:
    post = await get_generated_post(session, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")
    return _post_to_out(post)


# ── Daily trend posts ─────────────────────────────────────────────────────────

@router.get("/posts/{date}/{slug}", response_model=list[GeneratedPostOut])
async def list_posts_daily(date: str, slug: str, session: SessionDep, current_user: CurrentUser) -> list[GeneratedPostOut]:
    run_date = _date_parse(date)
    posts = await list_generated_posts(session, current_user.user_id, run_date=run_date, slug=slug)
    return [_post_to_out(p) for p in posts]


@router.post("/posts/{date}/{slug}/linkedin", response_model=GeneratedPostOut, status_code=201)
async def generate_daily_linkedin(
    date: str, slug: str, session: SessionDep, bg: BackgroundTasks, current_user: CurrentUser,
    body: GeneratePostIn = GeneratePostIn(),
) -> GeneratedPostOut:
    run_date = _date_parse(date)
    trend = await get_trend_by_slug(session, run_date, slug)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found.")

    chat_history, insights, style_profile, style_samples = await _load_context(
        session, current_user.user_id, trend, trend.run_id, slug
    )
    result = await generate_linkedin_post(
        trend, chat_history, insights, style_profile, style_samples,
        style=body.style,
        user_instructions=body.user_instructions,
    )
    evaluation = await evaluate_post_draft(
        result["content"], "linkedin", body.style, trend.headline, trend.one_liner
    )
    post_id = await create_generated_post(
        session, current_user.user_id, "linkedin", trend.run_id, run_date, slug,
        result["content"], result["hashtags"], headline=trend.headline,
        style_chosen=body.style, evaluation=evaluation,
    )
    bg.add_task(_bg_refresh_profile, current_user.user_id)
    post = await get_generated_post(session, post_id)
    log.info(
        "post_generated_saved",
        kind="linkedin",
        post_id=post_id,
        run_id=trend.run_id,
        run_date=run_date.isoformat(),
        slug=slug,
    )
    return _post_to_out(post)


@router.post("/posts/{date}/{slug}/blog", response_model=GeneratedPostOut, status_code=201)
async def generate_daily_blog(
    date: str, slug: str, session: SessionDep, bg: BackgroundTasks, current_user: CurrentUser,
    body: GeneratePostIn = GeneratePostIn(),
) -> GeneratedPostOut:
    run_date = _date_parse(date)
    trend = await get_trend_by_slug(session, run_date, slug)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found.")

    chat_history, insights, style_profile, style_samples = await _load_context(
        session, current_user.user_id, trend, trend.run_id, slug
    )
    result = await generate_blog_post(
        trend, chat_history, insights, style_profile, style_samples,
        style=body.style,
        user_instructions=body.user_instructions,
    )
    content = f"# {result['title']}\n\n{result['content_markdown']}"
    evaluation = await evaluate_post_draft(
        content, "blog", body.style, trend.headline, trend.one_liner
    )
    post_id = await create_generated_post(
        session, current_user.user_id, "blog", trend.run_id, run_date, slug,
        content, result["tags"], headline=trend.headline,
        style_chosen=body.style, evaluation=evaluation,
    )
    post = await get_generated_post(session, post_id)
    log.info(
        "post_generated_saved",
        kind="blog",
        post_id=post_id,
        run_id=trend.run_id,
        run_date=run_date.isoformat(),
        slug=slug,
    )
    return _post_to_out(post)


# ── Ad-hoc/search run posts ────────────────────────────────────────────────────

@router.get("/posts/runs/{run_id}/{slug}", response_model=list[GeneratedPostOut])
async def list_posts_run(run_id: str, slug: str, session: SessionDep, current_user: CurrentUser) -> list[GeneratedPostOut]:
    posts = await list_generated_posts(session, current_user.user_id, run_id=run_id, slug=slug)
    return [_post_to_out(p) for p in posts]


@router.post("/posts/runs/{run_id}/{slug}/linkedin", response_model=GeneratedPostOut, status_code=201)
async def generate_run_linkedin(
    run_id: str, slug: str, session: SessionDep, bg: BackgroundTasks, current_user: CurrentUser,
    body: GeneratePostIn = GeneratePostIn(),
) -> GeneratedPostOut:
    trends = await get_trends_for_run(session, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found for this run.")

    chat_history, insights, style_profile, style_samples = await _load_context(
        session, current_user.user_id, trend, run_id, slug
    )
    result = await generate_linkedin_post(
        trend, chat_history, insights, style_profile, style_samples,
        style=body.style,
        user_instructions=body.user_instructions,
    )
    evaluation = await evaluate_post_draft(
        result["content"], "linkedin", body.style, trend.headline, trend.one_liner
    )
    post_id = await create_generated_post(
        session, current_user.user_id, "linkedin", run_id, trend.run_date, slug,
        result["content"], result["hashtags"], headline=trend.headline,
        style_chosen=body.style, evaluation=evaluation,
    )
    bg.add_task(_bg_refresh_profile, current_user.user_id)
    post = await get_generated_post(session, post_id)
    log.info(
        "post_generated_saved",
        kind="linkedin",
        post_id=post_id,
        run_id=run_id,
        run_date=trend.run_date.isoformat(),
        slug=slug,
    )
    return _post_to_out(post)


@router.post("/posts/runs/{run_id}/{slug}/blog", response_model=GeneratedPostOut, status_code=201)
async def generate_run_blog(
    run_id: str, slug: str, session: SessionDep, bg: BackgroundTasks, current_user: CurrentUser,
    body: GeneratePostIn = GeneratePostIn(),
) -> GeneratedPostOut:
    trends = await get_trends_for_run(session, run_id)
    trend = next((t for t in trends if t.slug == slug), None)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend not found for this run.")

    chat_history, insights, style_profile, style_samples = await _load_context(
        session, current_user.user_id, trend, run_id, slug
    )
    result = await generate_blog_post(
        trend, chat_history, insights, style_profile, style_samples,
        style=body.style,
        user_instructions=body.user_instructions,
    )
    content = f"# {result['title']}\n\n{result['content_markdown']}"
    evaluation = await evaluate_post_draft(
        content, "blog", body.style, trend.headline, trend.one_liner
    )
    post_id = await create_generated_post(
        session, current_user.user_id, "blog", run_id, trend.run_date, slug,
        content, result["tags"], headline=trend.headline,
        style_chosen=body.style, evaluation=evaluation,
    )
    post = await get_generated_post(session, post_id)
    log.info(
        "post_generated_saved",
        kind="blog",
        post_id=post_id,
        run_id=run_id,
        run_date=trend.run_date.isoformat(),
        slug=slug,
    )
    return _post_to_out(post)


# ── Shared post edit + publish ─────────────────────────────────────────────────

@router.patch("/posts/{post_id}", response_model=GeneratedPostOut)
async def patch_post(post_id: int, body: GeneratedPostPatchIn, session: SessionDep, current_user: CurrentUser) -> GeneratedPostOut:
    post = await get_generated_post(session, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")

    # Re-evaluate the new content
    from datetime import date
    run_date_val = date.fromisoformat(post["run_date"])
    trend = await get_trend_by_slug(session, run_date_val, post["slug"])

    trend_headline = trend.headline if trend else post.get("headline", "")
    trend_one_liner = trend.one_liner if trend else ""

    style = post.get("style_chosen") or "leadership"
    evaluation = await evaluate_post_draft(
        body.content_markdown, post["kind"], style, trend_headline, trend_one_liner
    )

    await update_generated_post_content(session, post_id, current_user.user_id, body.content_markdown, body.tags, evaluation=evaluation)
    # User edits are high-quality style signal — record them
    await add_style_sample(session, current_user.user_id, "post_edit", body.content_markdown, source_ref=post_id)
    updated = await get_generated_post(session, post_id)
    return _post_to_out(updated)


@router.delete("/posts/{post_id}", response_model=DeletePostOut)
async def delete_post(post_id: int, session: SessionDep, current_user: CurrentUser) -> DeletePostOut:
    post = await get_generated_post(session, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")

    linkedin_deleted = False
    if post.get("linkedin_post_urn"):
        try:
            await li.delete_linkedin_post(session, current_user.user_id, post["linkedin_post_urn"])
            linkedin_deleted = True
        except Exception as exc:
            log.warning("linkedin_post_delete_failed", post_id=post_id, error=str(exc))

    deleted = await delete_generated_post(session, post_id, current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found.")
    log.info("post_deleted", post_id=post_id, linkedin_deleted=linkedin_deleted)
    return DeletePostOut(deleted=True, linkedin_deleted=linkedin_deleted)


@router.post("/posts/{post_id}/publish", response_model=PublishResponseOut)
async def publish_post_endpoint(
    post_id: int, session: SessionDep, current_user: CurrentUser, body: PublishPostIn = PublishPostIn()
) -> PublishResponseOut:
    post = await get_generated_post(session, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")
    if post["kind"] != "linkedin":
        raise HTTPException(status_code=400, detail="Only LinkedIn posts can be published via this endpoint.")

    publish_content = (body.content_override or "").strip() or post["content_markdown"]

    try:
        urn = await li.publish_post(
            session, current_user.user_id,
            publish_content,
            image_data_url=body.image_data_url,
            image_alt_text=body.image_alt_text,
        )
    except LinkedInAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await mark_post_published(session, post_id, current_user.user_id, urn)
    return PublishResponseOut(post_urn=urn, status="published")


# ── LinkedIn OAuth admin ───────────────────────────────────────────────────────

@router.get("/admin/linkedin/status", response_model=LinkedInStatusOut)
async def linkedin_status(session: SessionDep, current_user: CurrentUser) -> LinkedInStatusOut:
    global _li_status_cache
    if _li_status_cache and time.monotonic() < _li_status_cache[1]:
        return _li_status_cache[0]
    status = await li.get_connection_status(session, current_user.user_id)
    value = LinkedInStatusOut(**status)
    _li_status_cache = (value, time.monotonic() + _LI_STATUS_TTL)
    return value


@router.get("/admin/linkedin/authorize")
async def linkedin_authorize(current_user: CurrentUser, return_to: str = Query(default="/")) -> RedirectResponse:
    from ..config import get_settings
    settings = get_settings()
    if not settings.linkedin_client_id:
        raise HTTPException(status_code=503, detail="LinkedIn OAuth not configured. Set LINKEDIN_CLIENT_ID in .env.")
    safe_return_to = return_to if return_to.startswith("/") else "/"
    nonce = _new_oauth_nonce(safe_return_to)
    url = li.oauth_start(state=nonce)
    return RedirectResponse(url=url)


@router.get("/admin/linkedin/callback")
async def linkedin_callback(code: str, session: SessionDep, current_user: CurrentUser, state: str | None = None) -> RedirectResponse:
    from ..config import get_settings
    settings = get_settings()
    safe_return_to = "/"
    if state:
        resolved = _consume_oauth_nonce(state)
        if resolved:
            safe_return_to = resolved
        else:
            log.warning("linkedin_oauth_invalid_state", state_prefix=state[:8])
    base_redirect = f"{settings.frontend_base_url.rstrip('/')}{safe_return_to}"
    joiner = "&" if "?" in base_redirect else "?"
    try:
        await li.oauth_callback(session, current_user.user_id, code)
    except Exception as exc:
        log.error("linkedin_oauth_callback_failed", error=str(exc))
        msg = quote(str(exc))
        return RedirectResponse(url=f"{base_redirect}{joiner}li_auth=failed&msg={msg}", status_code=303)
    global _li_status_cache
    _li_status_cache = None  # force fresh status read after connect
    return RedirectResponse(url=f"{base_redirect}{joiner}li_auth=success", status_code=303)


# ── Background helper ─────────────────────────────────────────────────────────

async def _bg_refresh_profile(user_id: int) -> None:
    from ..db import _get_factory
    try:
        async with _get_factory()() as session:
            await refresh_profile_if_stale(session, user_id)
    except Exception as exc:
        log.warning("bg_profile_refresh_failed", error=str(exc))
