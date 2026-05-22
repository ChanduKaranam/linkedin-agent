from __future__ import annotations

import re
import urllib.parse
from typing import TYPE_CHECKING

import tldextract

from ...logging_setup import get_logger
from ...models import ScrapedPage

if TYPE_CHECKING:
    from crawl4ai import AsyncWebCrawler

log = get_logger(__name__)

_USER_AGENT = "LinkedInAgent-TrendBot/0.1 (+https://github.com/ChanduKaranam/linkedin-agent)"
_MIN_MARKDOWN_LEN = 80   # lowered from 200 — many real articles are short
_TAVILY_BATCH_SIZE = 20   # Tavily extract supports up to 20 URLs per call
_MAX_FETCH_BYTES = 1_500_000  # 1.5 MB hard cap on httpx response size


def _get_max_fetch_bytes() -> int:
    """On constrained hosts, cap HTML response size to reduce peak memory."""
    import os
    if os.environ.get("RENDER"):
        return 500_000  # 500 KB — enough for article text, skips bloated HTML
    return _MAX_FETCH_BYTES


def _extract_domain(url: str) -> str:
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    return m.group(1).strip() if m else ""


async def scrape_url(
    url: str,
    timeout: int = 25,
    *,
    crawler: "AsyncWebCrawler | None" = None,
) -> ScrapedPage | None:
    """Scrape a URL, returning clean markdown.

    Scrape chain (first success wins):
    - LOCAL (Crawl4AI available):
        1. Crawl4AI/Playwright — JS-rendered pages
        2. httpx + trafilatura/readability — static HTML, fast
        3. Tavily Extract — API-based, bypasses bot-blocks
        4. Jina AI Reader — proxy that bypasses CDN/bot-blocks
    - RENDER / datacenter (SCRAPE_USE_HTTPX_ONLY=true):
        1. Tavily Extract — most reliable on datacenter IPs
        2. Jina AI Reader — proxy bypass
        3. httpx + trafilatura — last resort (usually blocked)
    """
    from ...config import get_settings
    settings = get_settings()
    use_httpx_only = settings.scrape_use_httpx_only

    if use_httpx_only:
        # On datacenter IPs (Render etc.), httpx is almost always bot-blocked.
        # Try API-based scrapers first, fall back to httpx as last resort.
        return await _scrape_datacenter(url, timeout, settings)
    else:
        return await _scrape_local(url, timeout, crawler, settings)


async def _scrape_local(url, timeout, crawler, settings) -> ScrapedPage | None:
    """Scrape chain for local / VM with browser support."""
    # 1 — Crawl4AI (Playwright, handles JS-rendered pages)
    page = await _crawl4ai_scrape(url, timeout, crawler=crawler)
    if page and len(page.markdown) >= _MIN_MARKDOWN_LEN:
        log.info("scrape_success", url=url, method="crawl4ai", chars=len(page.markdown))
        return page

    # 2 — httpx + trafilatura/readability (fast, free, works on open sites)
    page = await _httpx_scrape(url, timeout)
    if page and len(page.markdown) >= _MIN_MARKDOWN_LEN:
        log.info("scrape_success", url=url, method=page.scrape_method, chars=len(page.markdown))
        return page

    # 3 — Tavily Extract (API-based, bypasses bot-blocks)
    page = await _tavily_scrape(url, timeout, api_key=settings.tavily_api_key)
    if page and len(page.markdown) >= _MIN_MARKDOWN_LEN:
        log.info("scrape_success", url=url, method="tavily", chars=len(page.markdown))
        return page

    # 4 — Jina AI Reader (proxy that bypasses CDN/Cloudflare blocks)
    page = await _jina_scrape(url, timeout, api_key=settings.jina_api_key)
    if page and len(page.markdown) >= _MIN_MARKDOWN_LEN:
        log.info("scrape_success", url=url, method="jina", chars=len(page.markdown))
        return page

    log.warning("scrape_failed", url=url, reason="insufficient_content")
    return None


async def _scrape_datacenter(url, timeout, settings) -> ScrapedPage | None:
    """Scrape chain optimized for datacenter IPs (Render, Railway, etc.).

    httpx is tried last because datacenter IPs are almost always bot-blocked.
    """
    # 1 — Tavily Extract (most reliable — Tavily handles bot-protection)
    page = await _tavily_scrape(url, timeout, api_key=settings.tavily_api_key)
    if page and len(page.markdown) >= _MIN_MARKDOWN_LEN:
        log.info("scrape_success", url=url, method="tavily", chars=len(page.markdown))
        return page

    # 2 — Jina AI Reader (proxy that bypasses CDN/Cloudflare blocks)
    page = await _jina_scrape(url, timeout, api_key=settings.jina_api_key)
    if page and len(page.markdown) >= _MIN_MARKDOWN_LEN:
        log.info("scrape_success", url=url, method="jina", chars=len(page.markdown))
        return page

    # 3 — httpx + trafilatura (last resort — usually bot-blocked on datacenter IPs)
    page = await _httpx_scrape(url, timeout)
    if page and len(page.markdown) >= _MIN_MARKDOWN_LEN:
        log.info("scrape_success", url=url, method=page.scrape_method, chars=len(page.markdown))
        return page

    log.warning("scrape_failed", url=url, reason="insufficient_content")
    return None


async def _crawl4ai_scrape(
    url: str,
    timeout: int,
    *,
    crawler: "AsyncWebCrawler | None" = None,
) -> ScrapedPage | None:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        run_cfg = CrawlerRunConfig(page_timeout=timeout * 1000, verbose=False)

        if crawler is not None:
            # Reuse the caller-managed shared browser — no async-with overhead
            result = await crawler.arun(url=url, config=run_cfg)
        else:
            # Standalone mode (e.g. chat-tool callers) — spawn and teardown
            browser_cfg = BrowserConfig(headless=True, user_agent=_USER_AGENT, verbose=False)
            async with AsyncWebCrawler(config=browser_cfg) as _crawler:
                result = await _crawler.arun(url=url, config=run_cfg)

        if not result.success:
            return None
        markdown = result.markdown or ""
        title = result.metadata.get("title", "") if result.metadata else ""
        return ScrapedPage(
            url=url,
            title=title,
            markdown=markdown,
            domain=_extract_domain(url),
            scrape_method="crawl4ai",
        )
    except Exception as exc:
        log.debug("crawl4ai_failed", url=url, error=str(exc)[:120])
        return None


async def _httpx_scrape(url: str, timeout: int) -> ScrapedPage | None:
    """Fetch HTML with httpx (streaming, 1.5 MB cap), then trafilatura → readability."""
    try:
        import httpx

        # Split timeout: quick connect, generous read — avoids 25 s hung-connect waste
        http_timeout = httpx.Timeout(connect=5.0, read=float(min(timeout, 20)))

        async with httpx.AsyncClient(
            timeout=http_timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            follow_redirects=True,
        ) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()

                # Reject non-HTML content early (PDFs, images, JSON APIs…)
                ct = resp.headers.get("content-type", "")
                if ct and "html" not in ct and "xml" not in ct:
                    log.debug("httpx_non_html", url=url, content_type=ct)
                    return None

                # Stream up to max_fetch_bytes — prevents loading large pages into memory
                max_fetch = _get_max_fetch_bytes()
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes(chunk_size=32_768):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= max_fetch:
                        break

                raw_bytes = b"".join(chunks)
                encoding = resp.encoding or "utf-8"
                html = raw_bytes.decode(encoding, errors="replace")

    except Exception as exc:
        log.debug("httpx_fetch_failed", url=url, error=str(exc)[:120])
        return None

    title = _extract_title(html)
    domain = _extract_domain(url)

    # Try trafilatura first
    text = _extract_trafilatura(html)
    if text and len(text) >= _MIN_MARKDOWN_LEN:
        return ScrapedPage(url=url, title=title, markdown=text, domain=domain,
                           scrape_method="httpx+trafilatura")

    # Fall back to readability-lxml
    text = _extract_readability(html)
    if text and len(text) >= _MIN_MARKDOWN_LEN:
        return ScrapedPage(url=url, title=title, markdown=text, domain=domain,
                           scrape_method="httpx+readability")

    # Return whatever we have, even if short — let caller decide
    best = text or _extract_trafilatura(html) or ""
    return ScrapedPage(url=url, title=title, markdown=best, domain=domain,
                       scrape_method="httpx+minimal") if best else None


def _extract_trafilatura(html: str) -> str:
    try:
        import trafilatura
        return trafilatura.extract(
            html,
            include_links=False,
            include_images=False,
            include_comments=False,
            no_fallback=False,
            favor_recall=True,   # be more aggressive about extracting text
        ) or ""
    except Exception:
        return ""


def _extract_readability(html: str) -> str:
    try:
        from readability import Document
        doc = Document(html)
        # readability returns HTML summary — strip tags
        summary_html = doc.summary()
        clean = re.sub(r"<[^>]+>", " ", summary_html)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
    except Exception:
        return ""


async def _tavily_scrape(url: str, timeout: int, api_key: str = "") -> ScrapedPage | None:
    """Fetch content via Tavily Extract API.

    Tavily's infrastructure handles bot-protection, CAPTCHAs, and JS rendering.
    Requires a Tavily API key (same one used for search).
    Cost: ~1 credit per 5 URLs (basic extraction).
    """
    if not api_key:
        log.debug("tavily_scrape_skipped", url=url, reason="no_api_key")
        return None
    try:
        import asyncio
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.extract(
                urls=[url],
                extract_depth="basic",
            ),
        )

        results = response.get("results", [])
        if not results:
            failed = response.get("failed_results", [])
            if failed:
                log.debug("tavily_extract_failed", url=url, failed=str(failed)[:200])
            return None

        result = results[0]
        markdown = result.get("raw_content", "").strip()
        if not markdown:
            return None

        # Extract title from first heading or use URL
        title = ""
        for line in markdown.splitlines()[:10]:
            if line.startswith("#"):
                title = line.lstrip("# ").strip()
                break

        return ScrapedPage(
            url=url,
            title=title,
            markdown=markdown,
            domain=_extract_domain(url),
            scrape_method="tavily",
        )
    except Exception as exc:
        log.debug("tavily_scrape_failed", url=url, error=str(exc)[:200])
        return None


async def tavily_batch_extract(
    urls: list[str],
    api_key: str = "",
) -> dict[str, ScrapedPage]:
    """Batch extract content via Tavily Extract API (up to 20 URLs per call).

    Returns a dict of url -> ScrapedPage for successful extractions.
    More efficient than individual scrape_url calls for the pipeline.
    """
    if not api_key or not urls:
        return {}

    results_map: dict[str, ScrapedPage] = {}
    try:
        import asyncio
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)

        # Process in batches of 20 (Tavily's limit)
        for i in range(0, len(urls), _TAVILY_BATCH_SIZE):
            batch = urls[i:i + _TAVILY_BATCH_SIZE]
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda batch=batch: client.extract(
                    urls=batch,
                    extract_depth="basic",
                ),
            )

            for result in response.get("results", []):
                url = result.get("url", "")
                markdown = result.get("raw_content", "").strip()
                if not markdown or len(markdown) < _MIN_MARKDOWN_LEN:
                    continue

                title = ""
                for line in markdown.splitlines()[:10]:
                    if line.startswith("#"):
                        title = line.lstrip("# ").strip()
                        break

                results_map[url] = ScrapedPage(
                    url=url,
                    title=title,
                    markdown=markdown,
                    domain=_extract_domain(url),
                    scrape_method="tavily_batch",
                )

            failed = response.get("failed_results", [])
            if failed:
                log.debug("tavily_batch_partial_failures",
                          count=len(failed),
                          sample=str(failed[:3])[:300])

        log.info("tavily_batch_extract_complete",
                 requested=len(urls), extracted=len(results_map))

    except Exception as exc:
        log.warning("tavily_batch_extract_failed", error=str(exc)[:200])

    return results_map


async def _jina_scrape(url: str, timeout: int, api_key: str = "") -> ScrapedPage | None:
    """Fetch via Jina AI Reader (r.jina.ai).

    Jina proxies the request through their own infrastructure, bypassing CDN
    bot-blocks and Cloudflare protections that reject datacenter IPs.
    Free tier: no API key needed (~20 RPM). Set JINA_API_KEY for higher limits.
    """
    try:
        import httpx

        jina_url = f"https://r.jina.ai/{url}"
        headers: dict[str, str] = {
            "Accept": "text/plain",
            "X-Return-Format": "markdown",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Jina fetches the target page itself, so allow extra time
        jina_timeout = httpx.Timeout(connect=10.0, read=float(min(timeout + 20, 45)))
        async with httpx.AsyncClient(timeout=jina_timeout, follow_redirects=True) as client:
            resp = await client.get(jina_url, headers=headers)
            if resp.status_code != 200:
                log.debug("jina_bad_status", url=url, status=resp.status_code,
                          body=resp.text[:200] if resp.text else "")
                return None
            markdown = resp.text.strip()
            if not markdown:
                log.debug("jina_empty_response", url=url)
                return None

        # Jina prepends "Title: <title>\nURL Source: <url>\n..." — extract the title
        title = ""
        for line in markdown.splitlines()[:6]:
            if line.startswith("Title:"):
                title = line[6:].strip()
                break

        return ScrapedPage(
            url=url,
            title=title,
            markdown=markdown,
            domain=_extract_domain(url),
            scrape_method="jina",
        )
    except Exception as exc:
        log.debug("jina_scrape_failed", url=url, error=str(exc)[:200])
        return None
