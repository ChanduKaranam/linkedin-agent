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
**Session date:** 2026-05-02

**Changes made:**
- `indexer.py` — wrapped `embed_batch(texts)` call in `asyncio.get_event_loop().run_in_executor(None, embed_batch, texts)`. Added `import asyncio` at the top.

**Reason:** `embed_batch` is synchronous CPU work (fastembed ONNX inference). Calling it directly on the asyncio event loop blocked the entire FastAPI server for 3-4 minutes per trend × 9 trends = ~30 minutes during each pipeline run. During this time, ALL HTTP requests (including `/health`) timed out, causing the frontend to show "Agent service is unreachable". Moving it to a thread executor frees the event loop immediately.

**Outcome:** Fix is in place. After the next backend restart, the server will remain responsive during RAG indexing. Existing in-progress pipeline runs at time of fix were not affected (the blocking code was already on the call stack).

**Watch out for:** `embed_batch` and `embed_query` in `embedder.py` are still synchronous — only `indexer.py` wraps them in executor. If `embed_query` (called by the retriever during chat) ever becomes slow, apply the same executor pattern there.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-02 | `indexer.py` | Wrapped embed_batch in run_in_executor to prevent event loop blocking during RAG indexing |
| — | — | Initial FOLDER.md created |
