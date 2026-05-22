from __future__ import annotations

import math
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastembed import TextEmbedding

from ..logging_setup import get_logger

log = get_logger(__name__)

_embed_model: "TextEmbedding | None" = None
_rerank_model = None

_EMBED_MODEL = "BAAI/bge-small-en-v1.5"
_RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
_TARGET_DIM = 384  # must match Vector(384) in db_models.py


def _use_api_embed() -> bool:
    """Return True when we should use API-based embedding (Render / low-RAM hosts)."""
    from ..config import get_settings
    return get_settings().rag_use_api_embed


# ── Local fastembed (used on dev machines) ────────────────────────────────────

def _get_embed() -> "TextEmbedding":
    global _embed_model
    if _embed_model is None:
        from fastembed import TextEmbedding
        _embed_model = TextEmbedding(_EMBED_MODEL)
    return _embed_model


def _get_reranker():
    global _rerank_model
    if _rerank_model is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        _rerank_model = TextCrossEncoder(_RERANK_MODEL)
    return _rerank_model


# ── API-based embedding via litellm (used on Render — 0 MB RAM) ──────────────

def _truncate_and_normalize(vec: list[float], dim: int = _TARGET_DIM) -> list[float]:
    """Truncate a high-dim vector to `dim` and L2-normalize.

    This is the standard Matryoshka truncation technique — works well for
    retrieval because modern embedding models are trained with this property.
    """
    truncated = vec[:dim]
    norm = math.sqrt(sum(x * x for x in truncated))
    if norm == 0:
        return truncated
    return [x / norm for x in truncated]


def _api_embed_sync(texts: list[str]) -> list[list[float]]:
    """Call Mistral embedding API synchronously (for use in run_in_executor)."""
    import litellm
    response = litellm.embedding(
        model="mistral/mistral-embed",
        input=texts,
    )
    vectors = [item["embedding"] for item in response.data]
    # Truncate 1024 → 384 to match the pgvector column
    return [_truncate_and_normalize(v) for v in vectors]


# ── Public API (auto-selects local vs API) ────────────────────────────────────

@lru_cache(maxsize=128)
def embed_query(text: str) -> list[float]:
    if _use_api_embed():
        return _api_embed_sync([text])[0]
    return list(next(iter(_get_embed().embed([text]))))


def embed_batch(texts: list[str]) -> list[list[float]]:
    if _use_api_embed():
        # Mistral embed supports up to 16384 tokens per batch — chunk to be safe
        results: list[list[float]] = []
        batch_size = 32
        for i in range(0, len(texts), batch_size):
            results.extend(_api_embed_sync(texts[i:i + batch_size]))
        return results
    return [list(v) for v in _get_embed().embed(texts)]


def rerank(query: str, passages: list[str]) -> list[float]:
    """Returns a float score per passage (higher = more relevant)."""
    scores = list(_get_reranker().rerank(query, passages))
    return scores
