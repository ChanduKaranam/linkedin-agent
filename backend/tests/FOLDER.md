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
_No changes recorded yet. Run `/end` at session close to record changes._

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| — | — | Initial documentation created |
