from __future__ import annotations

import secrets
from datetime import date, datetime, timezone

from sqlalchemy import and_, case, delete, func, select, tuple_, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import AuthSession, ChatMessage, Chunk, GeneratedPost, Insight, LinkedInAccount, LogEvent, Run, StyleProfile, StyleSample, Trend, User
from .logging_setup import get_logger
from .models import PersistedTrend, RunState, Source, UserInfo

log = get_logger(__name__)
_POST_KINDS = {"linkedin", "blog"}


# ── DB init / migration ───────────────────────────────────────────────────────

async def init_db() -> None:
    """Run Alembic upgrade head. Called from app lifespan."""
    import subprocess
    import sys
    from pathlib import Path

    backend_dir = Path(__file__).parent.parent.parent

    def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
        )

    def _target_from_upgrade_log(stderr_text: str) -> str | None:
        import re
        match = re.search(r"Running upgrade\s+\S*\s*->\s*([0-9a-zA-Z_]+)", stderr_text)
        return match.group(1) if match else None

    result = _run_alembic("upgrade", "head")
    if result.returncode == 0:
        return

    stderr = result.stderr or ""
    is_duplicate_schema_error = (
        ("DuplicateTableError" in stderr or "DuplicateColumnError" in stderr)
        and "already exists" in stderr
    )
    if is_duplicate_schema_error:
        stamped: set[str] = set()
        while True:
            target = _target_from_upgrade_log(stderr)
            if not target or target in stamped:
                break
            stamp = _run_alembic("stamp", target)
            if stamp.returncode != 0:
                raise RuntimeError(
                    "Alembic stamp failed during duplicate-table recovery:\n"
                    f"{stamp.stderr}"
                )
            stamped.add(target)
            retry = _run_alembic("upgrade", "head")
            if retry.returncode == 0:
                return
            stderr = retry.stderr or ""
            is_duplicate_schema_error = (
                ("DuplicateTableError" in stderr or "DuplicateColumnError" in stderr)
                and "already exists" in stderr
            )
            if not is_duplicate_schema_error:
                raise RuntimeError(
                    "Alembic upgrade failed after duplicate-table recovery:\n"
                    f"{stderr}"
                )

    raise RuntimeError(f"Alembic upgrade failed:\n{stderr}")


# ── Runs ──────────────────────────────────────────────────────────────────────

async def create_run(
    session: AsyncSession,
    run_id: str,
    run_date: date,
    topic: str,
    kind: str = "daily",
    user_id: int | None = None,
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
        user_id=user_id,
        run_date=run_date,
        topic=topic,
        kind=kind,
        state="pending",
        started_at=datetime.now(timezone.utc),
    ))
    await session.commit()


async def find_adhoc_run(
    session: AsyncSession, topic: str, run_date: date, user_id: int | None = None
) -> RunState | None:
    conditions = [Run.kind == "adhoc", Run.topic == topic, Run.run_date == run_date, Run.state != "failed"]
    if user_id is not None:
        conditions.append(Run.user_id == user_id)
    row = (await session.execute(
        select(Run)
        .where(*conditions)
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
    # Truncate error text — full tracebacks go to log_events
    if last_error and len(last_error) > 2000:
        last_error = last_error[:1997] + "..."
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


async def list_adhoc_runs(session: AsyncSession, user_id: int | None = None, limit: int = 50) -> list[RunState]:
    # Include in-progress runs so the history sidebar can show their progress.
    conditions = [Run.kind == "adhoc", Run.state != "failed"]
    if user_id is not None:
        conditions.append(Run.user_id == user_id)
    rows = (await session.execute(
        select(Run)
        .where(*conditions)
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
        user_id=row.user_id,
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

async def count_trends_for_run(session: AsyncSession, run_id: str) -> int:
    result = await session.execute(
        select(func.count()).select_from(Trend).where(Trend.run_id == run_id)
    )
    return result.scalar_one() or 0


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


async def get_trend_summaries_for_run(
    session: AsyncSession, run_id: str
) -> list[tuple[str, str, str, int]]:
    """Lightweight projection for list endpoints — avoids loading detailed_markdown."""
    rows = (await session.execute(
        select(Trend.slug, Trend.headline, Trend.one_liner, func.jsonb_array_length(Trend.sources_json))
        .where(Trend.run_id == run_id)
        .order_by(Trend.id)
    )).all()
    return [(slug, headline, one_liner, src_count or 0) for slug, headline, one_liner, src_count in rows]


async def get_trend_by_run_and_slug(
    session: AsyncSession, run_id: str, slug: str
) -> PersistedTrend | None:
    row = (await session.execute(
        select(Trend).where(Trend.run_id == run_id, Trend.slug == slug)
    )).scalar_one_or_none()
    return _orm_to_trend(row) if row else None


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
    # Query dates directly from the trends table so that partially-completed or
    # stuck runs don't hide real trend data that was already persisted.
    rows = (await session.execute(
        select(Trend.run_date)
        .distinct()
        .order_by(Trend.run_date.desc())
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
    user_id: int,
    run_id: str,
    run_date: date,
    slug: str,
    role: str,
    content: str,
    citations: list | None = None,
    used_web: bool = False,
) -> int:
    msg = ChatMessage(
        user_id=user_id,
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
    user_id: int,
    run_date: date | None = None,
    run_id: str | None = None,
    slug: str | None = None,
    limit: int = 100,
) -> list[dict]:
    if run_id:
        q = select(ChatMessage).where(
            ChatMessage.user_id == user_id,
            ChatMessage.run_id == run_id, ChatMessage.slug == slug
        )
    else:
        q = select(ChatMessage).where(
            ChatMessage.user_id == user_id,
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
    user_id: int,
    run_id: str,
    run_date: date,
    slug: str,
    user_perspective: str,
    summary: str = "",
    tags: list[str] | None = None,
) -> int:
    now = datetime.now(timezone.utc)
    ins = Insight(
        user_id=user_id,
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
    user_id: int,
    run_date: date | None = None,
    run_id: str | None = None,
    slug: str | None = None,
) -> list[dict]:
    if run_id:
        q = select(Insight).where(
            Insight.user_id == user_id,
            Insight.run_id == run_id, Insight.slug == slug,
        )
    else:
        q = select(Insight).where(
            Insight.user_id == user_id,
            Insight.run_date == run_date, Insight.slug == slug,
        )
    rows = (await session.execute(q.order_by(Insight.created_at))).scalars().all()
    return [_orm_to_insight(r) for r in rows]


async def list_all_insights(
    session: AsyncSession,
    user_id: int,
    limit: int = 300,
) -> list[dict]:
    rows = (
        await session.execute(
            select(Insight)
            .where(Insight.user_id == user_id)
            .order_by(Insight.created_at.desc())
            .limit(limit)
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
    user_id: int,
    slug: str,
    limit: int = 200,
) -> list[dict]:
    """All insights for a slug across ALL runs for this user — used for post generation context."""
    q = (
        select(Insight)
        .where(Insight.user_id == user_id, Insight.slug == slug)
        .order_by(Insight.created_at)
        .limit(limit)
    )
    rows = (await session.execute(q)).scalars().all()
    return [_orm_to_insight(r) for r in rows]


async def list_chat_messages_by_slug(
    session: AsyncSession,
    user_id: int,
    slug: str,
    limit: int = 400,
) -> list[dict]:
    """All chat messages for a slug across ALL runs for this user — captures the full conversation history."""
    q = (
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id, ChatMessage.slug == slug)
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
    user_id: int,
    run_date: date | None = None,
    run_id: str | None = None,
    slug: str | None = None,
) -> int:
    if run_id:
        result = await session.execute(
            delete(ChatMessage).where(
                ChatMessage.user_id == user_id,
                ChatMessage.run_id == run_id, ChatMessage.slug == slug,
            )
        )
    else:
        result = await session.execute(
            delete(ChatMessage).where(
                ChatMessage.user_id == user_id,
                ChatMessage.run_date == run_date, ChatMessage.slug == slug,
            )
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
    user_id: int,
    source: str,
    text: str,
    source_ref: int | None = None,
) -> int | None:
    import hashlib
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    # Skip duplicate samples within the last 90 days
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    existing = (await session.execute(
        select(StyleSample.id)
        .where(StyleSample.user_id == user_id, StyleSample.text_hash == text_hash, StyleSample.created_at >= cutoff)
        .limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return None
    sample = StyleSample(
        user_id=user_id,
        source=source,
        source_ref=source_ref,
        text=text,
        text_hash=text_hash,
        created_at=datetime.now(timezone.utc),
    )
    session.add(sample)
    await session.flush()
    await session.commit()
    return sample.id


async def count_style_samples(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(StyleSample).where(StyleSample.user_id == user_id)
    )
    return result.scalar_one()


async def get_recent_style_samples(session: AsyncSession, user_id: int, limit: int = 80) -> list[dict]:
    rows = (await session.execute(
        select(StyleSample)
        .where(StyleSample.user_id == user_id)
        .order_by(StyleSample.created_at.desc())
        .limit(limit)
    )).scalars().all()
    return [{"id": r.id, "source": r.source, "text": r.text, "created_at": r.created_at.isoformat()} for r in rows]


async def get_style_samples_for_few_shot(session: AsyncSession, user_id: int, k: int = 5) -> list[str]:
    """Return k samples for the user: longest texts from recent entries for representative few-shot examples."""
    rows = (await session.execute(
        select(StyleSample)
        .where(StyleSample.user_id == user_id)
        .order_by(StyleSample.created_at.desc())
        .limit(k * 4)
    )).scalars().all()
    if not rows:
        return []
    sorted_rows = sorted(rows, key=lambda r: len(r.text), reverse=True)
    return [r.text for r in sorted_rows[:k]]


# ── Style profile ──────────────────────────────────────────────────────────────

async def get_style_profile(session: AsyncSession, user_id: int) -> dict | None:
    row = (await session.execute(select(StyleProfile).where(StyleProfile.user_id == user_id))).scalar_one_or_none()
    if row is None:
        return None
    return {
        "profile_markdown": row.profile_markdown,
        "sample_count_at_last_refresh": row.sample_count_at_last_refresh,
        "updated_at": row.updated_at.isoformat(),
    }


async def upsert_style_profile(
    session: AsyncSession,
    user_id: int,
    profile_markdown: str,
    sample_count: int,
) -> None:
    now = datetime.now(timezone.utc)
    existing = (await session.execute(select(StyleProfile).where(StyleProfile.user_id == user_id))).scalar_one_or_none()
    if existing:
        existing.profile_markdown = profile_markdown
        existing.sample_count_at_last_refresh = sample_count
        existing.updated_at = now
    else:
        session.add(StyleProfile(
            user_id=user_id,
            profile_markdown=profile_markdown,
            sample_count_at_last_refresh=sample_count,
            updated_at=now,
        ))
    await session.commit()


# ── Generated posts ────────────────────────────────────────────────────────────

async def create_generated_post(
    session: AsyncSession,
    user_id: int,
    kind: str,
    run_id: str,
    run_date: date,
    slug: str,
    content_markdown: str,
    tags: list[str],
    headline: str = "",
    style_chosen: str | None = None,
    evaluation: dict | None = None,
) -> int:
    if kind not in _POST_KINDS:
        raise ValueError(f"Invalid generated post kind: {kind!r}")
    if not slug or not slug.strip():
        raise ValueError("slug must be a non-empty string")

    now = datetime.now(timezone.utc)
    post = GeneratedPost(
        user_id=user_id,
        kind=kind,
        run_id=run_id,
        run_date=run_date,
        slug=slug,
        headline=headline or slug.replace("-", " ").title(),
        content_markdown=content_markdown,
        tags_json=tags,
        status="draft",
        style_chosen=style_chosen,
        evaluation_json=evaluation,
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
    user_id: int,
    run_date: date | None = None,
    run_id: str | None = None,
    slug: str | None = None,
) -> list[dict]:
    if run_id:
        q = select(GeneratedPost).where(
            GeneratedPost.user_id == user_id,
            GeneratedPost.run_id == run_id, GeneratedPost.slug == slug,
        )
    else:
        q = select(GeneratedPost).where(
            GeneratedPost.user_id == user_id,
            GeneratedPost.run_date == run_date, GeneratedPost.slug == slug,
        )
    rows = (await session.execute(q.order_by(GeneratedPost.created_at.desc()))).scalars().all()
    return [_orm_to_post(r) for r in rows]


async def list_all_generated_posts(
    session: AsyncSession,
    user_id: int,
    kind: str,
    limit: int = 100,
) -> list[dict]:
    """All posts of one kind for a user with their stored headline, newest-updated first.

    Reads headline directly from generated_posts — no join needed. Headlines are
    snapshotted at creation time so they survive trend deletion (>15-day retention).
    """
    if kind not in _POST_KINDS:
        raise ValueError(f"Invalid generated post kind: {kind!r}")
    if limit <= 0:
        log.warning("list_all_generated_posts_invalid_limit", limit=limit)
        return []

    post_rows = (
        await session.execute(
            select(GeneratedPost)
            .where(GeneratedPost.user_id == user_id, GeneratedPost.kind == kind)
            .order_by(GeneratedPost.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    return [_orm_to_post(p) for p in post_rows]


async def update_generated_post_content(
    session: AsyncSession,
    post_id: int,
    user_id: int,
    content_markdown: str,
    tags: list[str],
    status: str = "edited",
    evaluation: dict | None = None,
) -> None:
    await session.execute(
        update(GeneratedPost)
        .where(GeneratedPost.id == post_id, GeneratedPost.user_id == user_id)
        .values(content_markdown=content_markdown, tags_json=tags, status=status, evaluation_json=evaluation, updated_at=datetime.now(timezone.utc))
    )
    await session.commit()


async def mark_post_published(session: AsyncSession, post_id: int, user_id: int, linkedin_post_urn: str) -> None:
    await session.execute(
        update(GeneratedPost)
        .where(GeneratedPost.id == post_id, GeneratedPost.user_id == user_id)
        .values(status="published", linkedin_post_urn=linkedin_post_urn, updated_at=datetime.now(timezone.utc))
    )
    await session.commit()


async def delete_generated_post(session: AsyncSession, post_id: int, user_id: int) -> bool:
    result = await session.execute(
        delete(GeneratedPost).where(GeneratedPost.id == post_id, GeneratedPost.user_id == user_id)
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
        "headline": row.headline or row.slug.replace("-", " ").title(),
        "content_markdown": row.content_markdown,
        "tags": row.tags_json,
        "status": row.status,
        "linkedin_post_urn": row.linkedin_post_urn,
        "style_chosen": row.style_chosen,
        "evaluation": row.evaluation_json,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


# ── LinkedIn account ────────────────────────────────────────────────────────────

async def get_linkedin_account(session: AsyncSession, user_id: int) -> dict | None:
    row = (await session.execute(select(LinkedInAccount).where(LinkedInAccount.user_id == user_id))).scalar_one_or_none()
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
    user_id: int,
    access_token: str,
    refresh_token: str | None,
    expires_at: datetime,
    member_urn: str,
    member_name: str | None = None,
) -> None:
    existing = (await session.execute(select(LinkedInAccount).where(LinkedInAccount.user_id == user_id))).scalar_one_or_none()
    if existing:
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.expires_at = expires_at
        existing.member_urn = member_urn
        if member_name is not None:
            existing.member_name = member_name
    else:
        session.add(LinkedInAccount(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            member_urn=member_urn,
            member_name=member_name,
        ))
    await session.commit()


async def clear_linkedin_account(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(LinkedInAccount).where(LinkedInAccount.user_id == user_id))
    await session.commit()


# ── Retention ──────────────────────────────────────────────────────────────────

async def purge_data_older_than(session: AsyncSession, cutoff_date: date) -> dict[str, int]:
    """Delete all runs/trends/chunks/chat_messages/insights older than cutoff_date.

    Generated posts, style samples, and the style profile are intentionally left
    untouched — they must survive the 15-day trend window.

    Returns per-table deleted row counts for logging.
    """
    chat_result = await session.execute(
        delete(ChatMessage).where(ChatMessage.run_date < cutoff_date)
    )
    insight_result = await session.execute(
        delete(Insight).where(Insight.run_date < cutoff_date)
    )
    # Deleting a Run cascades to its Trend rows (ondelete=CASCADE), and each Trend
    # cascades to its Chunk rows — so we only need to delete the Run.
    run_result = await session.execute(
        delete(Run).where(Run.run_date < cutoff_date)
    )
    await session.commit()
    return {
        "chat_messages": chat_result.rowcount or 0,
        "insights": insight_result.rowcount or 0,
        "runs": run_result.rowcount or 0,
    }


# ── Auth ────────────────────────────────────────────────────────────────────────

async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    return (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return (await session.execute(select(User).where(User.user_id == user_id))).scalar_one_or_none()


_SESSION_TTL_DAYS = 30


async def create_session(session: AsyncSession, username: str) -> str:
    from datetime import timedelta
    user = await get_user_by_username(session, username)
    if user is None:
        raise ValueError(f"User '{username}' not found")
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session.add(AuthSession(
        token=token,
        user_id=user.user_id,
        username=username,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=_SESSION_TTL_DAYS),
    ))
    await session.commit()
    return token


async def get_session_user(session: AsyncSession, token: str) -> User | None:
    try:
        row = (
            await session.execute(
                select(AuthSession).where(AuthSession.token == token)
            )
        ).scalar_one_or_none()
    except (SQLAlchemyError, ConnectionResetError) as exc:
        # Render/Neon can occasionally reset TLS handshakes; retry once.
        log.warning("auth_session_lookup_retry", error=str(exc))
        await session.rollback()
        row = (
            await session.execute(
                select(AuthSession).where(AuthSession.token == token)
            )
        ).scalar_one_or_none()
    if row is None:
        return None
    # Reject expired sessions (may not have expires_at if created before 0008 migration)
    if hasattr(row, "expires_at") and row.expires_at and row.expires_at < datetime.now(timezone.utc):
        await session.execute(delete(AuthSession).where(AuthSession.token == token))
        await session.commit()
        return None
    # Avoid writing on every single authenticated request; this endpoint is
    # hot under polling UIs and can saturate the DB pool.
    from .config import get_settings
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    min_interval = timedelta(seconds=max(get_settings().auth_last_seen_update_seconds, 30))
    if row.last_seen_at is None or (now - row.last_seen_at) >= min_interval:
        await session.execute(
            update(AuthSession)
            .where(AuthSession.token == token)
            .values(last_seen_at=now)
        )
        await session.commit()
    return await get_user_by_id(session, row.user_id)


async def get_session_username(session: AsyncSession, token: str) -> str | None:
    """Lightweight auth check used by request dependency.

    Avoids a join/query on users for every protected request. Returns username if
    token exists and is not expired, otherwise None.
    """
    info = await get_session_user_info(session, token)
    return info.username if info else None


async def get_session_user_info(session: AsyncSession, token: str) -> UserInfo | None:
    """Returns user_id + username from a valid session token, or None if expired/missing."""
    try:
        row = (
            await session.execute(
                select(AuthSession).where(AuthSession.token == token)
            )
        ).scalar_one_or_none()
    except (SQLAlchemyError, ConnectionResetError) as exc:
        log.warning("auth_session_info_retry", error=str(exc))
        await session.rollback()
        row = (
            await session.execute(
                select(AuthSession).where(AuthSession.token == token)
            )
        ).scalar_one_or_none()
    if row is None:
        return None
    if hasattr(row, "expires_at") and row.expires_at and row.expires_at < datetime.now(timezone.utc):
        await session.execute(delete(AuthSession).where(AuthSession.token == token))
        await session.commit()
        return None

    from .config import get_settings
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    min_interval = timedelta(seconds=max(get_settings().auth_last_seen_update_seconds, 30))
    if row.last_seen_at is None or (now - row.last_seen_at) >= min_interval:
        await session.execute(
            update(AuthSession)
            .where(AuthSession.token == token)
            .values(last_seen_at=now)
        )
        await session.commit()
    return UserInfo(user_id=row.user_id, username=row.username)


async def purge_expired_sessions(session: AsyncSession) -> int:
    result = await session.execute(
        delete(AuthSession).where(AuthSession.expires_at < datetime.now(timezone.utc))
    )
    await session.commit()
    return result.rowcount or 0


async def delete_session(session: AsyncSession, token: str) -> None:
    await session.execute(delete(AuthSession).where(AuthSession.token == token))
    await session.commit()


# ── Log events ──────────────────────────────────────────────────────────────

async def purge_old_logs(session: AsyncSession, info_days: int = 7, warn_days: int = 30) -> dict[str, int]:
    """Delete log_events rows older than level-specific retention windows.

    INFO/DEBUG → info_days; WARNING/ERROR/CRITICAL → warn_days.
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    info_cutoff = now - timedelta(days=info_days)
    warn_cutoff = now - timedelta(days=warn_days)

    info_result = await session.execute(
        delete(LogEvent).where(
            LogEvent.level.in_(["DEBUG", "INFO"]),
            LogEvent.ts < info_cutoff,
        )
    )
    warn_result = await session.execute(
        delete(LogEvent).where(
            LogEvent.level.in_(["WARNING", "ERROR", "CRITICAL"]),
            LogEvent.ts < warn_cutoff,
        )
    )
    await session.commit()
    return {
        "log_events_info": info_result.rowcount or 0,
        "log_events_warn": warn_result.rowcount or 0,
    }


async def get_log_events(
    session: AsyncSession,
    level: str | None = None,
    logger_name: str | None = None,
    since: datetime | None = None,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[LogEvent]:
    stmt = select(LogEvent).order_by(LogEvent.ts.desc()).limit(limit).offset(offset)
    if level:
        stmt = stmt.where(LogEvent.level == level.upper())
    if logger_name:
        stmt = stmt.where(LogEvent.logger_name.ilike(f"%{logger_name}%"))
    if since:
        stmt = stmt.where(LogEvent.ts >= since)
    if q:
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                LogEvent.event.ilike(f"%{q}%"),
                LogEvent.message.ilike(f"%{q}%"),
            )
        )
    return list((await session.execute(stmt)).scalars().all())
