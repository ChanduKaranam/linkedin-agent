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
  └── Yes → Tavily (news topic, 2-day window, basic depth)
  └── No  → DuckDuckGo DDGS (text search, safesearch=moderate)
Both fall back to empty list on exception (never crash the pipeline).
```

## Last Session Changes
_No changes recorded yet. Run `/end` at session close to record changes._

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| — | — | Initial documentation created |
