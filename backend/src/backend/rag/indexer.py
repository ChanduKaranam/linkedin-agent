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
    total_chunks = 0
    now = datetime.now(timezone.utc)
    embed_batch_size = 32

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
        for start in range(0, len(texts), embed_batch_size):
            text_batch = texts[start : start + embed_batch_size]
            vectors = await loop.run_in_executor(None, embed_batch, text_batch)
            chunk_rows = [
                Chunk(
                    trend_id=trend_id,
                    run_id=run_id,
                    source_url=source.url,
                    source_title=source.title,
                    source_domain=source.domain,
                    chunk_index=start + idx,
                    text=text,
                    embedding=vec,
                    created_at=now,
                )
                for idx, (text, vec) in enumerate(zip(text_batch, vectors))
            ]
            session.add_all(chunk_rows)
            await session.flush()
            total_chunks += len(chunk_rows)

        # Keep transaction/object memory bounded per source.
        await session.commit()

    log.info("trend_indexed", trend_id=trend_id, chunks=total_chunks)
    return total_chunks
