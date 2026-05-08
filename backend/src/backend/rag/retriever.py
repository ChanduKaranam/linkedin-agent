from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db_models import Chunk
from .embedder import embed_query, rerank


@dataclass
class RetrievedChunk:
    chunk_id: int
    trend_id: int
    source_url: str
    source_title: str
    source_domain: str
    text: str
    score: float


async def retrieve(
    session: AsyncSession,
    trend_id: int,
    query: str,
    k: int = 6,
    candidate_k: int = 20,
) -> list[RetrievedChunk]:
    """Hybrid retrieval: dense + BM25 → RRF → rerank → top-k."""
    loop = asyncio.get_event_loop()
    qvec = await loop.run_in_executor(None, embed_query, query)

    # Dense: top-candidate_k by cosine similarity
    dense_rows = (await session.execute(
        select(Chunk)
        .where(Chunk.trend_id == trend_id)
        .order_by(Chunk.embedding.op("<=>") (qvec))
        .limit(candidate_k)
    )).scalars().all()

    # BM25: top-candidate_k by ts_rank_cd
    tsquery = func.plainto_tsquery("english", query)
    bm25_rows = (await session.execute(
        select(Chunk, func.ts_rank_cd(Chunk.tsv, tsquery).label("bm25"))
        .where(
            and_(
                Chunk.trend_id == trend_id,
                Chunk.tsv.op("@@")(tsquery),
            )
        )
        .order_by(text("bm25 DESC"))
        .limit(candidate_k)
    )).all()
    bm25_chunks = [row[0] for row in bm25_rows]

    # RRF fusion
    rrf_scores: dict[int, float] = {}
    for rank, chunk in enumerate(dense_rows, start=1):
        rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + 1.0 / (60 + rank)
    for rank, chunk in enumerate(bm25_chunks, start=1):
        rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + 1.0 / (60 + rank)

    # Merge unique candidates ordered by RRF score
    seen: set[int] = set()
    candidates: list[Chunk] = []
    for chunk in [*dense_rows, *bm25_chunks]:
        if chunk.id not in seen:
            seen.add(chunk.id)
            candidates.append(chunk)
    candidates.sort(key=lambda c: rrf_scores.get(c.id, 0.0), reverse=True)
    candidates = candidates[:30]

    if not candidates:
        return []

    if get_settings().rag_disable_rerank:
        ranked = [(c, rrf_scores.get(c.id, 0.0)) for c in candidates]
    else:
        # Cross-encoder rerank — run in executor to avoid blocking the event loop
        scores = await loop.run_in_executor(None, partial(rerank, query, [c.text for c in candidates]))
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

    return [
        RetrievedChunk(
            chunk_id=c.id,
            trend_id=c.trend_id,
            source_url=c.source_url,
            source_title=c.source_title,
            source_domain=c.source_domain,
            text=c.text,
            score=float(s),
        )
        for c, s in ranked[:k]
    ]
