from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..db_models import Chunk
from ..logging_setup import get_logger
from ..models import Source
from .chunker import chunk_markdown
from .embedder import embed_batch

log = get_logger(__name__)


async def index_trend(
    session: AsyncSession,
    trend_id: int,
    run_id: str,
    sources: list[Source],
    cache_dir: Path,
) -> int:
    """Chunk + embed all cached source pages for a trend. Idempotent: replaces existing chunks."""
    all_chunks: list[Chunk] = []
    now = datetime.now(timezone.utc)

    for source in sources:
        cache_file = cache_dir / f"{hashlib.md5(source.url.encode()).hexdigest()}.md"
        if not cache_file.exists():
            continue
        try:
            md = cache_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        texts = chunk_markdown(md)
        if not texts:
            continue

        # Delete existing chunks for this source so we can re-index safely
        await session.execute(
            delete(Chunk).where(Chunk.trend_id == trend_id, Chunk.source_url == source.url)
        )

        loop = asyncio.get_event_loop()
        vectors = await loop.run_in_executor(None, embed_batch, texts)
        for idx, (text, vec) in enumerate(zip(texts, vectors)):
            all_chunks.append(Chunk(
                trend_id=trend_id,
                run_id=run_id,
                source_url=source.url,
                source_title=source.title,
                source_domain=source.domain,
                chunk_index=idx,
                text=text,
                embedding=vec,
                created_at=now,
            ))

    session.add_all(all_chunks)
    await session.commit()
    log.info("trend_indexed", trend_id=trend_id, chunks=len(all_chunks))
    return len(all_chunks)
