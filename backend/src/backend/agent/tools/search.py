from __future__ import annotations

import asyncio
from typing import Any

from ...logging_setup import get_logger
from ...models import DiscoveredUrl

log = get_logger(__name__)

_USER_AGENT = "LinkedInAgent-TrendBot/0.1"


async def search_web(query: str, max_results: int = 10) -> list[DiscoveredUrl]:
    """Search the web for a query. Uses Tavily if API key is set, else DuckDuckGo."""
    from ...config import get_settings

    settings = get_settings()
    if settings.tavily_api_key:
        return await _tavily_search(query, max_results, settings.tavily_api_key)
    return await _ddgs_search(query, max_results)


async def _ddgs_search(query: str, max_results: int) -> list[DiscoveredUrl]:
    from ddgs import DDGS

    try:
        loop = asyncio.get_event_loop()
        results: list[dict[str, Any]] = await loop.run_in_executor(
            None,
            lambda: list(
                DDGS().text(
                    query,
                    max_results=max_results,
                    safesearch="moderate",
                )
            ),
        )
        return [
            DiscoveredUrl(
                url=r.get("href", r.get("url", "")),
                title=r.get("title", ""),
                snippet=r.get("body", r.get("description", "")),
                source_query=query,
            )
            for r in results
            if r.get("href") or r.get("url")
        ]
    except Exception as exc:
        log.warning("ddgs_search_failed", query=query, error=str(exc))
        return []


async def _tavily_search(query: str, max_results: int, api_key: str) -> list[DiscoveredUrl]:
    from tavily import TavilyClient

    try:
        loop = asyncio.get_event_loop()
        client = TavilyClient(api_key=api_key)
        response = await loop.run_in_executor(
            None,
            lambda: client.search(
                query,
                max_results=max_results,
                search_depth="basic",
                topic="news",
                days=2,
            ),
        )
        return [
            DiscoveredUrl(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("content", ""),
                source_query=query,
            )
            for r in response.get("results", [])
            if r.get("url")
        ]
    except Exception as exc:
        log.warning("tavily_search_failed", query=query, error=str(exc))
        return await _ddgs_search(query, max_results)
