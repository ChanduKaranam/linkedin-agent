from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import and_, case, delete, func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import ChatMessage, GeneratedPost, Insight, LinkedInAccount, Run, StyleProfile, StyleSample, Trend
from .logging_setup import get_logger
from .models import PersistedTrend, RunState, Source

log = get_logger(__name__)
_POST_KINDS = {"linkedin", "blog"}


# ── DB init / migration ───────────────────────────────────────────────────────

async def init_db() -> None:
    """Run Alembic upgrade head. Called from app lifespan."""
    import subprocess
    import sys
    from pathlib import Path

    backend_dir = Path(__file__).parent.parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Alembic upgrade failed:\n{result.stderr}")


# ── Runs ──────────────────────────────────────────────────────────────────────

async def create_run(
    session: AsyncSession,
    run_id: str,
    run_date: date,
    topic: str,
    kind: str = "daily",
) -> None:
    if kind == "daily":
        # Delete ALL same-date daily runs regardless of topic.  A topic rename in
        # topics.yaml must not leave an orphaned completed row alongside the new
        # pending one — that causes get_latest_daily_run to see duplicate rows.
        await session.execute(
            delete(Run).where(Run.run_date == run_date, Run.kind == "daily")
        )
    else:
        await session.execute(
            delete(Run).where(Run.run_date == run_date, Run.topic == topic, Run.kind == kind)
        )
    session.add(Run(
        run_id=run_id,
        run_date=run_date,
        topic=topic,
        kind=kind,
        state="pending",
        started_at=datetime.now(timezone.utc),
    ))
    await session.commit()


async def find_adhoc_run(
    session: AsyncSession, topic: str, run_date: date
) -> RunState | None:
    row = (await session.execute(
        select(Run)
        .where(Run.kind == "adhoc", Run.topic == topic, Run.run_date == run_date, Run.state != "failed")
        .order_by(Run.started_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    return _orm_to_run(row) if row else None


async def update_run_state(
    session: AsyncSession,
    run_id: str,
    state: str,
    trend_count: int | None = None,
    warnings: int | None = None,
    last_error: str | None = None,
) -> None:
    finished_at = (
        datetime.now(timezone.utc)
        if state in ("completed", "failed", "completed_with_warnings")
        else None
    )
    values: dict = {"state": state, "finished_at": finished_at, "last_error": last_error}
    if trend_count is not None:
        values["trend_count"] = trend_count
    if warnings is not None:
        values["warnings"] = warnings
    await session.execute(update(Run).where(Run.run_id == run_id).values(**values))
    await session.commit()


async def get_run(session: AsyncSession, run_id: str) -> RunState | None:
    row = (await session.execute(select(Run).where(Run.run_id == run_id))).scalar_one_or_none()
    return _orm_to_run(row) if row else None


async def get_latest_daily_run(session: AsyncSession) -> RunState | None:
    # Prefer completed rows over in-progress rows for the same date.
    # Without a tiebreaker, Postgres non-deterministically returns either row
    # when two daily runs share run_date (e.g. a completed + a newly spawned pending).
    priority = case(
        (Run.state.in_(["completed", "completed_with_warnings"]), 0),
        (Run.state == "failed", 2),
        else_=1,
    )
    row = (await session.execute(
        select(Run)
        .where(Run.kind == "daily")
        .order_by(Run.run_date.desc(), priority.asc(), Run.started_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    return _orm_to_run(row) if row else None


async def get_latest_completed_run(session: AsyncSession) -> RunState | None:
    row = (await session.execute(
        select(Run)
        .where(Run.kind == "daily", Run.state.in_(["completed", "completed_with_warnings"]))
        .order_by(Run.run_date.desc())
        .limit(1)
    )).scalar_one_or_none()
    return _orm_to_run(row) if row else None


async def get_stale_runs(session: AsyncSession) -> list[RunState]:
    rows = (await session.execute(
        select(Run).where(Run.state.not_in(["completed", "completed_with_warnings", "failed"]))
    )).scalars().all()
    return [_orm_to_run(r) for r in rows]


async def list_runs(session: AsyncSession, limit: int = 20) -> list[RunState]:
    rows = (await session.execute(
        select(Run).order_by(Run.started_at.desc()).limit(limit)
    )).scalars().all()
    return [_orm_to_run(r) for r in rows]


async def list_adhoc_runs(session: AsyncSession, limit: int = 50) -> list[RunState]:
    # Include in-progress runs so the history sidebar can show their progress.
    rows = (await session.execute(
        select(Run)
        .where(Run.kind == "adhoc", Run.state != "failed")
        .order_by(Run.started_at.desc())
        .limit(limit)
    )).scalars().all()
    return [_orm_to_run(r) for r in rows]


async def run_exists_for_date(session: AsyncSession, run_date: date, topic: str) -> bool:
    # Topic filter intentionally dropped for daily runs: a renamed topic in
    # topics.yaml must not cause a false "no run" result that triggers a spurious
    # catch-up run alongside the existing completed run.
    row = (await session.execute(
        select(Run.run_id)
        .where(Run.run_date == run_date, Run.kind == "daily", Run.state != "failed")
        .limit(1)
    )).scalar_one_or_none()
    return row is not None


def _orm_to_run(row: Run) -> RunState:
    return RunState(
        run_id=row.run_id,
        run_date=row.run_date,
        topic=row.topic,
        kind=row.kind,
        state=row.state,
        started_at=row.started_at,
        finished_at=row.finished_at,
        trend_count=row.trend_count,
        warnings=row.warnings,
        last_error=row.last_error,
    )


# ── Trends ────────────────────────────────────────────────────────────────────

async def upsert_trend(session: AsyncSession, trend: PersistedTrend) -> int:
    """Insert trend, or bump seen_again if fingerprint exists within window. Returns new trend id."""
    from .config import get_topic_config
    window = get_topic_config().dedup.cross_day_window

    existing = (await session.execute(
        select(Trend.id)
        .where(
            Trend.fingerprint == trend.fingerprint,
            Trend.run_date >= func.current_date() - window,
        )
    )).scalar_one_or_none()

    if existing:
        await session.execute(
            update(Trend).where(Trend.id == existing).values(seen_again=Trend.seen_again + 1)
        )
        await session.commit()
        return existing

    new_trend = Trend(
        run_id=trend.run_id,
        run_date=trend.run_date,
        slug=trend.slug,
        headline=trend.headline,
        one_liner=trend.one_liner,
        detailed_markdown=trend.detailed_markdown,
        key_points_json=trend.key_points,
        sources_json=[s.model_dump() for s in trend.sources],
        fingerprint=trend.fingerprint,
        seen_again=0,
        created_at=datetime.now(timezone.utc),
    )
    session.add(new_trend)
    await session.flush()  # populates new_trend.id
    await session.commit()
    return new_trend.id


async def get_trends_for_run(session: AsyncSession, run_id: str) -> list[PersistedTrend]:
    rows = (await session.execute(
        select(Trend).where(Trend.run_id == run_id).order_by(Trend.id)
    )).scalars().all()
    return [_orm_to_trend(r) for r in rows]


async def get_trends_for_date(session: AsyncSession, run_date: date) -> list[PersistedTrend]:
    rows = (await session.execute(
        select(Trend).where(Trend.run_date == run_date).order_by(Trend.id)
    )).scalars().all()
    return [_orm_to_trend(r) for r in rows]


async def get_trend_by_slug(
    session: AsyncSession, run_date: date, slug: str
) -> PersistedTrend | None:
    row = (await session.execute(
        select(Trend).where(Trend.run_date == run_date, Trend.slug == slug)
    )).scalar_one_or_none()
    return _orm_to_trend(row) if row else None


async def get_available_dates(session: AsyncSession) -> list[date]:
    rows = (await session.execute(
        select(Run.run_date)
        .where(Run.kind == "daily", Run.state.in_(["completed", "completed_with_warnings"]))
        .distinct()
        .order_by(Run.run_date.desc())
    )).scalars().all()
    return list(rows)


async def fingerprint_exists_in_window(
    session: AsyncSession, fingerprint: str, window_days: int
) -> bool:
    row = (await session.execute(
        select(Trend.id)
        .where(
            Trend.fingerprint == fingerprint,
            Trend.run_date >= func.current_date() - window_days,
        )
        .limit(1)
    )).scalar_one_or_none()
    return row is not None


async def get_recent_headlines(session: AsyncSession, window_days: int) -> list[str]:
    rows = (await session.execute(
        select(Trend.headline)
        .where(Trend.run_date >= func.current_date() - window_days)
    )).scalars().all()
    return list(rows)


async def unique_slug(session: AsyncSession, headline: str, run_date: date) -> str:
    from slugify import slugify
    base = slugify(headline)[:80]
    slug = base
    n = 1
    while (await session.execute(
        select(Trend.id).where(Trend.run_date == run_date, Trend.slug == slug).limit(1)
    )).scalar_one_or_none() is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


def _orm_to_trend(row: Trend) -> PersistedTrend:
    sources = [Source(**s) for s in row.sources_json]
    return PersistedTrend(
        id=row.id,
        run_id=row.run_id,
        run_date=row.run_date,
        slug=row.slug,
        headline=row.headline,
        one_liner=row.one_liner,
        detailed_markdown=row.detailed_markdown,
        key_points=row.key_points_json,
        sources=sources,
        fingerprint=row.fingerprint,
        seen_again=row.seen_again,
        created_at=row.created_at,
    )


# ── Chat messages ──────────────────────────────────────────────────────────────

async def append_chat_message(
    session: AsyncSession,
    run_id: str,
    run_date: date,
    slug: str,
    role: str,
    content: str,
    citations: list | None = None,
    used_web: bool = False,
) -> int:
    msg = ChatMessage(
        run_id=run_id,
        run_date=run_date,
        slug=slug,
        role=role,
        content=content,
        citations_json=citations or [],
        used_web=used_web,
        created_at=datetime.now(timezone.utc),
    )
    session.add(msg)
    await session.flush()
    await session.commit()
    return msg.id


async def list_chat_messages(
    session: AsyncSession,
    run_date: date | None = None,
    run_id: str | None = None,
    slug: str | None = None,
    limit: int = 100,
) -> list[dict]:
    if run_id:
        q = select(ChatMessage).where(
            ChatMessage.run_id == run_id, ChatMessage.slug == slug
        )
    else:
        q = select(ChatMessage).where(
            ChatMessage.run_date == run_date, ChatMessage.slug == slug
        )
    rows = (await session.execute(q.order_by(ChatMessage.created_at).limit(limit))).scalars().all()
    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "citations": r.citations_json,
            "used_web": r.used_web,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


# ── Insights ───────────────────────────────────────────────────────────────────

async def create_insight(
    session: AsyncSession,
    run_id: str,
    run_date: date,
    slug: str,
    user_perspective: str,
    summary: str = "",
    tags: list[str] | None = None,
) -> int:
    now = datetime.now(timezone.utc)
    ins = Insight(
        run_id=run_id,
        run_date=run_date,
        slug=slug,
        user_perspective=user_perspective,
        summary=summary,
        tags_json=tags or [],
        created_at=now,
        updated_at=now,
    )
    session.add(ins)
    await session.flush()
    await session.commit()
    return ins.id


async def list_insights(
    session: AsyncSession,
    run_date: date | None = None,
    run_id: str | None = None,
    slug: str | None = None,
) -> list[dict]:
    if run_id:
        q = select(Insight).where(Insight.run_id == run_id, Insight.slug == slug)
    else:
        q = select(Insight).where(Insight.run_date == run_date, Insight.slug == slug)
    rows = (await session.execute(q.order_by(Insight.created_at))).scalars().all()
    return [_orm_to_insight(r) for r in rows]


async def list_all_insights(
    session: AsyncSession,
    limit: int = 300,
) -> list[dict]:
    rows = (
        await session.execute(
            select(Insight).order_by(Insight.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    if not rows:
        return []

    run_ids = list({r.run_id for r in rows})
    run_rows = (
        await session.execute(select(Run).where(Run.run_id.in_(run_ids)))
    ).scalars().all()
    run_map = {r.run_id: r for r in run_rows}

    # Headline by (run_date, slug). If multiple matches exist, keep the first.
    pairs = list({(r.run_date, r.slug) for r in rows})
    trend_rows = (
        await session.execute(
            select(Trend.run_date, Trend.slug, Trend.headline).where(
                tuple_(Trend.run_date, Trend.slug).in_(pairs)  # type: ignore[name-defined]
            )
        )
    ).all()
    headline_map: dict[tuple[date, str], str] = {}
    for tr in trend_rows:
        key = (tr.run_date, tr.slug)
        if key not in headline_map:
            headline_map[key] = tr.headline

    out: list[dict] = []
    for r in rows:
        run = run_map.get(r.run_id)
        run_kind = (run.kind if run else "daily")
        context_kind = "search" if run_kind == "adhoc" else "trend"
        out.append({
            **_orm_to_insight(r),
            "run_id": r.run_id,
            "run_date": r.run_date.isoformat(),
            "slug": r.slug,
            "context_kind": context_kind,
            "topic": run.topic if run else "",
            "headline": headline_map.get((r.run_date, r.slug), r.slug.replace("-", " ").title()),
        })
    return out


async def list_insights_by_slug(
    session: AsyncSession,
    slug: str,
    limit: int = 200,
) -> list[dict]:
    """All insights for a slug across ALL runs — used for post generation context."""
    q = (
        select(Insight)
        .where(Insight.slug == slug)
        .order_by(Insight.created_at)
        .limit(limit)
    )
    rows = (await session.execute(q)).scalars().all()
    return [_orm_to_insight(r) for r in rows]


async def list_chat_messages_by_slug(
    session: AsyncSession,
    slug: str,
    limit: int = 400,
) -> list[dict]:
    """All chat messages for a slug across ALL runs — captures the full conversation history."""
    q = (
        select(ChatMessage)
        .where(ChatMessage.slug == slug)
        .order_by(ChatMessage.created_at)
        .limit(limit)
    )
    rows = (await session.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "citations": r.citations_json,
            "used_web": r.used_web,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


async def delete_chat_messages(
    session: AsyncSession,
    run_date: date | None = None,
    run_id: str | None = None,
    slug: str | None = None,
) -> int:
    if run_id:
        result = await session.execute(
            delete(ChatMessage).where(ChatMessage.run_id == run_id, ChatMessage.slug == slug)
        )
    else:
        result = await session.execute(
            delete(ChatMessage).where(ChatMessage.run_date == run_date, ChatMessage.slug == slug)
        )
    await session.commit()
    return result.rowcount or 0


def _orm_to_insight(r: "Insight") -> dict:  # type: ignore[name-defined]
    return {
        "id": r.id,
        "user_perspective": r.user_perspective,
        "summary": r.summary,
        "tags": r.tags_json,
        "created_at": r.created_at.isoformat(),
    }


# ── Style samples ──────────────────────────────────────────────────────────────

async def add_style_sample(
    session: AsyncSession,
    source: str,
    text: str,
    source_ref: int | None = None,
) -> int:
    sample = StyleSample(
        source=source,
        source_ref=source_ref,
        text=text,
        created_at=datetime.now(timezone.utc),
    )
    session.add(sample)
    await session.flush()
    await session.commit()
    return sample.id


async def count_style_samples(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(StyleSample))
    return result.scalar_one()


async def get_recent_style_samples(session: AsyncSession, limit: int = 80) -> list[dict]:
    rows = (await session.execute(
        select(StyleSample).order_by(StyleSample.created_at.desc()).limit(limit)
    )).scalars().all()
    return [{"id": r.id, "source": r.source, "text": r.text, "created_at": r.created_at.isoformat()} for r in rows]


async def get_style_samples_for_few_shot(session: AsyncSession, k: int = 5) -> list[str]:
    """Return k samples: longest texts from recent entries for representative few-shot examples."""
    rows = (await session.execute(
        select(StyleSample).order_by(StyleSample.created_at.desc()).limit(k * 4)
    )).scalars().all()
    if not rows:
        return []
    sorted_rows = sorted(rows, key=lambda r: len(r.text), reverse=True)
    return [r.text for r in sorted_rows[:k]]


# ── Style profile ──────────────────────────────────────────────────────────────

async def get_style_profile(session: AsyncSession) -> dict | None:
    row = (await session.execute(select(StyleProfile).where(StyleProfile.id == 1))).scalar_one_or_none()
    if row is None:
        return None
    return {
        "profile_markdown": row.profile_markdown,
        "sample_count_at_last_refresh": row.sample_count_at_last_refresh,
        "updated_at": row.updated_at.isoformat(),
    }


async def upsert_style_profile(
    session: AsyncSession,
    profile_markdown: str,
    sample_count: int,
) -> None:
    now = datetime.now(timezone.utc)
    existing = (await session.execute(select(StyleProfile).where(StyleProfile.id == 1))).scalar_one_or_none()
    if existing:
        existing.profile_markdown = profile_markdown
        existing.sample_count_at_last_refresh = sample_count
        existing.updated_at = now
    else:
        session.add(StyleProfile(
            id=1,
            profile_markdown=profile_markdown,
            sample_count_at_last_refresh=sample_count,
            updated_at=now,
        ))
    await session.commit()


# ── Generated posts ────────────────────────────────────────────────────────────

async def create_generated_post(
    session: AsyncSession,
    kind: str,
    run_id: str,
    run_date: date,
    slug: str,
    content_markdown: str,
    tags: list[str],
) -> int:
    if kind not in _POST_KINDS:
        raise ValueError(f"Invalid generated post kind: {kind!r}")
    if not slug or not slug.strip():
        raise ValueError("slug must be a non-empty string")

    now = datetime.now(timezone.utc)
    post = GeneratedPost(
        kind=kind,
        run_id=run_id,
        run_date=run_date,
        slug=slug,
        content_markdown=content_markdown,
        tags_json=tags,
        status="draft",
        created_at=now,
        updated_at=now,
    )
    session.add(post)
    await session.flush()
    await session.commit()
    return post.id


async def get_generated_post(session: AsyncSession, post_id: int) -> dict | None:
    row = (await session.execute(select(GeneratedPost).where(GeneratedPost.id == post_id))).scalar_one_or_none()
    return _orm_to_post(row) if row else None


async def list_generated_posts(
    session: AsyncSession,
    run_date: date | None = None,
    run_id: str | None = None,
    slug: str | None = None,
) -> list[dict]:
    if run_id:
        q = select(GeneratedPost).where(GeneratedPost.run_id == run_id, GeneratedPost.slug == slug)
    else:
        q = select(GeneratedPost).where(GeneratedPost.run_date == run_date, GeneratedPost.slug == slug)
    rows = (await session.execute(q.order_by(GeneratedPost.created_at.desc()))).scalars().all()
    return [_orm_to_post(r) for r in rows]


async def list_all_generated_posts(
    session: AsyncSession,
    kind: str,
    limit: int = 100,
) -> list[dict]:
    """All posts of one kind with their Trend headline, newest-updated first.

    Uses a plain SELECT on generated_posts (no join) then a single IN query to
    batch-fetch headlines — avoids ORM/driver quirks with mixed entity+column selects.
    """
    if kind not in _POST_KINDS:
        raise ValueError(f"Invalid generated post kind: {kind!r}")
    if limit <= 0:
        log.warning("list_all_generated_posts_invalid_limit", limit=limit)
        return []

    # Step 1: fetch the posts
    post_rows = (
        await session.execute(
            select(GeneratedPost)
            .where(GeneratedPost.kind == kind)
            .order_by(GeneratedPost.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    if not post_rows:
        return []

    # Step 2: batch-fetch trend headlines for all distinct slugs
    slugs = list({p.slug for p in post_rows})
    trend_rows = (
        await session.execute(
            select(Trend.slug, Trend.headline).where(Trend.slug.in_(slugs))
        )
    ).all()
    # Most recent headline per slug (there can be multiple runs per slug)
    headline_map: dict[str, str] = {}
    for row in trend_rows:
        if row.slug not in headline_map:
            headline_map[row.slug] = row.headline

    # Step 3: assemble result — fall back to title-cased slug when no trend found
    return [
        {
            **_orm_to_post(p),
            "headline": headline_map.get(p.slug) or p.slug.replace("-", " ").title(),
        }
        for p in post_rows
    ]


async def update_generated_post_content(
    session: AsyncSession,
    post_id: int,
    content_markdown: str,
    tags: list[str],
    status: str = "edited",
) -> None:
    await session.execute(
        update(GeneratedPost)
        .where(GeneratedPost.id == post_id)
        .values(content_markdown=content_markdown, tags_json=tags, status=status, updated_at=datetime.now(timezone.utc))
    )
    await session.commit()


async def mark_post_published(session: AsyncSession, post_id: int, linkedin_post_urn: str) -> None:
    await session.execute(
        update(GeneratedPost)
        .where(GeneratedPost.id == post_id)
        .values(status="published", linkedin_post_urn=linkedin_post_urn, updated_at=datetime.now(timezone.utc))
    )
    await session.commit()


async def delete_generated_post(session: AsyncSession, post_id: int) -> bool:
    result = await session.execute(
        delete(GeneratedPost).where(GeneratedPost.id == post_id)
    )
    await session.commit()
    return (result.rowcount or 0) > 0


def _orm_to_post(row: GeneratedPost) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "run_id": row.run_id,
        "run_date": row.run_date.isoformat(),
        "slug": row.slug,
        "content_markdown": row.content_markdown,
        "tags": row.tags_json,
        "status": row.status,
        "linkedin_post_urn": row.linkedin_post_urn,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


# ── LinkedIn account ────────────────────────────────────────────────────────────

async def get_linkedin_account(session: AsyncSession) -> dict | None:
    row = (await session.execute(select(LinkedInAccount).where(LinkedInAccount.id == 1))).scalar_one_or_none()
    if row is None:
        return None
    return {
        "access_token": row.access_token,
        "refresh_token": row.refresh_token,
        "expires_at": row.expires_at,
        "member_urn": row.member_urn,
        "member_name": row.member_name,
    }


async def upsert_linkedin_account(
    session: AsyncSession,
    access_token: str,
    refresh_token: str | None,
    expires_at: datetime,
    member_urn: str,
    member_name: str | None = None,
) -> None:
    existing = (await session.execute(select(LinkedInAccount).where(LinkedInAccount.id == 1))).scalar_one_or_none()
    if existing:
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.expires_at = expires_at
        existing.member_urn = member_urn
        if member_name is not None:
            existing.member_name = member_name
    else:
        session.add(LinkedInAccount(
            id=1,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            member_urn=member_urn,
            member_name=member_name,
        ))
    await session.commit()


async def clear_linkedin_account(session: AsyncSession) -> None:
    await session.execute(delete(LinkedInAccount).where(LinkedInAccount.id == 1))
    await session.commit()
