# backend/src/backend/agent/tools/

## Purpose
Reusable async I/O tools used by both the pipeline and the chat agent.

## Files
| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `search.py` | `search_web(query, max_results)` — uses Tavily if `TAVILY_API_KEY` is set, otherwise falls back to DuckDuckGo (`ddgs`). Returns `list[DiscoveredUrl]`. |
| `scrape.py` | `scrape_url(url, timeout)` — uses Crawl4AI (`AsyncWebCrawler`) to fetch and convert a page to Markdown. Returns `ScrapedPage` or `None` on failure. |
| `robots.py` | `is_allowed(url, rps)` — checks robots.txt via `urllib.robotparser`. `polite_delay(domain, rps)` — per-domain rate limiting using an in-memory timestamp dict. |

## Search Priority Logic (search.py)
```
TAVILY_API_KEY set?
  └── Yes → Tavily (news topic, days=1, basic depth)
  └── No  → DuckDuckGo DDGS (text search, safesearch=moderate, timelimit="d")
Both fall back to empty list on exception (never crash the pipeline).
```

## Last Session Changes
**Session date:** 2026-05-02

**Changes made:**
- `search.py` — two recency fixes: (1) Tavily `days=2` → `days=1` so only articles from the last 24h are returned; (2) DuckDuckGo now passes `timelimit="d"` (last day) — previously had no date filter and could return results from any date.

**Reason:** Both search backends were returning old articles. Tavily was fetching up to 2 days back; DuckDuckGo had no limit at all. This was a key source of "old news" appearing in the daily brief.

**Outcome:** Discovery phase now produces URLs from the last 24 hours. Combined with the scrape cache TTL and LLM cutoff changes, the full pipeline now strongly filters for fresh content.

**Watch out for:** `timelimit="d"` on DuckDuckGo may return fewer results on slow news days. If `max_sources_per_run` isn't met, the pipeline still proceeds (it only fails if > 50% of discovered URLs fail to scrape).

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-02 | `search.py` | Tavily days=1; DuckDuckGo timelimit="d" — both search backends now return only last-24h results |
| — | — | Initial documentation created |
