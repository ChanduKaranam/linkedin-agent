from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastembed import TextEmbedding, SparseTextEmbedding

_embed_model: "TextEmbedding | None" = None
_rerank_model = None

_EMBED_MODEL = "BAAI/bge-small-en-v1.5"
_RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


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


def embed_query(text: str) -> list[float]:
    return list(next(iter(_get_embed().embed([text]))))


def embed_batch(texts: list[str]) -> list[list[float]]:
    return [list(v) for v in _get_embed().embed(texts)]


def rerank(query: str, passages: list[str]) -> list[float]:
    """Returns a float score per passage (higher = more relevant)."""
    scores = list(_get_reranker().rerank(query, passages))
    return scores
