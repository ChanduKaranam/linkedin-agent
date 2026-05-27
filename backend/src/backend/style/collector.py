from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..logging_setup import get_logger
from ..storage import add_style_sample

log = get_logger(__name__)

_MIN_TEXT_LEN = 20


async def record_sample(
    session: AsyncSession,
    user_id: int,
    source: str,
    text: str,
    source_ref: int | None = None,
) -> None:
    """Append a piece of user writing to the user's style corpus. Skips very short texts."""
    text = text.strip()
    if len(text) < _MIN_TEXT_LEN:
        return
    try:
        await add_style_sample(session, user_id, source, text, source_ref)
        log.debug("style_sample_recorded", source=source, chars=len(text))
    except Exception as exc:
        log.warning("style_sample_record_failed", source=source, error=str(exc))
