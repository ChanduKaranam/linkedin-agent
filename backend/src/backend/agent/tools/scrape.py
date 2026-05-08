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
_MAX_FETCH_BYTES = 1_500_000  # 1.5 MB hard cap on httpx response size


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

    If `crawler` (a shared AsyncWebCrawler) is provided it is reused directly
    (no per-URL Chromium startup cost). When omitted, a per-call crawler is
    spawned (backwards-compatible for chat-tool callers).

    When `SCRAPE_USE_HTTPX_ONLY=true` is set, Crawl4AI is skipped entirely.
    This is required on Render free tier where Playwright's CPU usage starves
    the asyncio event loop and breaks concurrent DB connections.
    """
    from ...config import get_settings
    use_httpx_only = get_settings().scrape_use_httpx_only

    # 1 — Crawl4AI (Playwright, handles JS-rendered pages)
    if not use_httpx_only:
        page = await _crawl4ai_scrape(url, timeout, crawler=crawler)
        if page and len(page.markdown) >= _MIN_MARKDOWN_LEN:
            log.info("scrape_success", url=url, method="crawl4ai", chars=len(page.markdown))
            return page

    # 2 & 3 — static fetcher with two extractors
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

                # Stream up to _MAX_FETCH_BYTES — prevents loading 5 MB pages
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes(chunk_size=32_768):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= _MAX_FETCH_BYTES:
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
