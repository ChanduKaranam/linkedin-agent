# backend/tests/

## Purpose
Pytest test suite covering storage, deduplication, pipeline logic, and API routes. Uses both real SQLite (in-memory or temp file) and mocked HTTP calls.

## Subfolders
| Folder | Role |
|---|---|
| `fixtures/` | Static test data: JSON search results, scraped HTML pages |

## Files
| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `conftest.py` | Pytest fixtures: in-memory DB, `TopicConfig` instance, `AsyncClient` for API tests |
| `test_dedup.py` | Unit tests for `compute_fingerprint` and `deduplicate_urls` |
| `test_pipeline_mocked.py` | Pipeline tests with `search_web` and `scrape_url` mocked — verifies phase transitions and state updates |
| `test_search_routes.py` | FastAPI `TestClient` / `AsyncClient` tests for `/search` endpoints |
| `test_storage.py` | Tests for all `storage.py` functions against a real SQLite in-memory DB |

## Running Tests
```bash
cd backend
pytest                        # all tests
pytest tests/test_storage.py  # single file
pytest -x                     # stop on first failure
```

## Last Session Changes
**Session date:** 2026-05-02

**Changes made:**
- `test_dedup.py` — fully rewritten. Old tests called `compute_fingerprint(headline, sources)` with two args. `compute_fingerprint` is now headline-only (no `sources` param), so all old tests broke. New tests: `test_fingerprint_same_headline` (stability), `test_fingerprint_different_headlines` (sensitivity), `test_fingerprint_case_and_punctuation_insensitive` (normalization), plus the two `deduplicate_urls` tests (unchanged logic, preserved).

**Reason:** `compute_fingerprint` signature changed this session — the `sources: list[Source]` argument was removed because the fingerprint was being computed from all run sources (not trend-specific sources), making cross-day dedup effectively non-functional. Headline-only fingerprint is now stable across runs.

**Outcome:** Tests updated and passing. The old `test_fingerprint_utm_stripped` and `test_fingerprint_order_independent` tests were removed since UTM stripping and source ordering are no longer part of the fingerprint.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-02 | `test_dedup.py` | Updated for headline-only compute_fingerprint signature; removed source-based test cases |
| — | — | Initial documentation created |
