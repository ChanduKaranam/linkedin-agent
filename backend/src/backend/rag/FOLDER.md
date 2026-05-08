# backend/src/backend/rag/

## Purpose
RAG (Retrieval-Augmented Generation) layer. Handles chunking scraped Markdown into passages, generating embeddings via fastembed (local ONNX model), and hybrid vector+BM25 retrieval for the chat agent. The indexer runs after each trend is persisted; the retriever is called on every chat turn.

## Files
| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `indexer.py` | `index_trend(session, trend_id, run_id, sources, cache_dir)` — reads cached Markdown for all sources, chunks them, embeds each chunk batch in a thread executor, and bulk-inserts `Chunk` rows. Idempotent: deletes existing chunks for each source before re-inserting. |
| `embedder.py` | `embed_batch(texts) -> list[list[float]]` — synchronous fastembed call using `BAAI/bge-small-en-v1.5` (384-dim). `embed_query(text)` — single-query embedding for retrieval. `rerank(query, passages)` — cross-encoder reranking using `Xenova/ms-marco-MiniLM-L-6-v2`. Models are lazy-loaded singletons. |
| `chunker.py` | `chunk_markdown(md) -> list[str]` — splits Markdown into passage-sized chunks suitable for embedding. |
| `retriever.py` | Hybrid search combining pgvector cosine similarity and BM25 (`tsv` column). Returns ranked `Chunk` rows for the chat agent's context window. |

## Key Design Notes
- **`embed_batch` is CPU-intensive**: fastembed runs ONNX inference locally. It MUST be called via `asyncio.get_event_loop().run_in_executor(None, embed_batch, texts)` in `indexer.py` — calling it directly on the event loop blocks ALL HTTP requests for minutes.
- **828 chunks per trend**: each trend indexes ALL run sources (not just its own), so with ~23 sources × ~36 chunks each = ~828 chunks. This is intentional for RAG coverage but makes indexing slow (~3-4 min per trend).
- **Idempotent indexing**: `DELETE chunks WHERE trend_id = X AND source_url = Y` runs before each insert, so re-running index_trend is safe.

## Last Session Changes
**Session date:** 2026-05-08

**Changes made:**
- `retriever.py` — added `import asyncio` and `from functools import partial`. Wrapped `embed_query(query)` call in `await loop.run_in_executor(None, embed_query, query)`. Wrapped `rerank(query, texts)` call in `await loop.run_in_executor(None, partial(rerank, query, texts))`.

**Reason:** `embed_query` and `rerank` call fastembed's ONNX inference synchronously. On every chat turn this blocked the event loop for 50–200ms — long enough to delay all other HTTP requests, including SSE stream writes. The indexer already used executor for `embed_batch` (since 2026-05-02), but the retriever's two calls were overlooked.

**Watch out for:** Both `embed_query` and `rerank` are now in executors. `indexer.py` also uses executor (added 2026-05-02). The delete-before-insert in `indexer.py` should be wrapped in a transaction so readers don't see a window with no chunks — this is a known issue to revisit.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-08 | `retriever.py` | Wrapped `embed_query` and `rerank` in `run_in_executor` — was blocking the event loop on every chat turn |
| 2026-05-02 | `indexer.py` | Wrapped embed_batch in run_in_executor to prevent event loop blocking during RAG indexing |
| — | — | Initial FOLDER.md created |
