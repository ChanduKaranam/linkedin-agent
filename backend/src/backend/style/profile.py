from __future__ import annotations

import litellm
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.prompts import STYLE_DISTILL_SYSTEM, STYLE_DISTILL_USER
from ..config import get_topic_config
from ..logging_setup import get_logger
from ..storage import (
    count_style_samples,
    get_recent_style_samples,
    get_style_profile,
    upsert_style_profile,
)

log = get_logger(__name__)

_REFRESH_GROWTH_RATIO = 1.05  # refresh when sample count grows 5% (keep profile fresh)
_MIN_SAMPLES_TO_PROFILE = 3   # don't profile until we have at least 3 samples


async def get_profile_text(session: AsyncSession) -> str:
    """Return the current distilled style profile text, or empty string."""
    profile = await get_style_profile(session)
    return profile["profile_markdown"] if profile else ""


async def refresh_profile_if_stale(session: AsyncSession, force: bool = False) -> bool:
    """Check staleness; if stale (or forced), re-distil the profile. Returns True if refreshed."""
    total = await count_style_samples(session)
    if total < _MIN_SAMPLES_TO_PROFILE and not force:
        return False

    profile = await get_style_profile(session)
    last_count = profile["sample_count_at_last_refresh"] if profile else 0

    if not force and total < last_count * _REFRESH_GROWTH_RATIO:
        return False

    samples = await get_recent_style_samples(session, limit=80)
    sample_texts = [s["text"] for s in samples]

    numbered = "\n\n".join(f"[{i+1}] {t}" for i, t in enumerate(sample_texts))
    user_msg = STYLE_DISTILL_USER.format(count=len(sample_texts), samples=numbered)

    cfg = get_topic_config()
    try:
        response = await litellm.acompletion(
            model=cfg.models.summarize,
            messages=[
                {"role": "system", "content": STYLE_DISTILL_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        )
        profile_md = (response.choices[0].message.content or "").strip()
        await upsert_style_profile(session, profile_md, total)
        log.info("style_profile_refreshed", sample_count=total)
        return True
    except Exception as exc:
        log.warning("style_profile_refresh_failed", error=str(exc))
        return False
