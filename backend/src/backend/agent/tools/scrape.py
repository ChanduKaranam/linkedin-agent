from __future__ import annotations

import re
import urllib.parse

import tldextract

from ...logging_setup import get_logger
from ...models import ScrapedPage

log = get_logger(__name__)

_USER_AGENT = "LinkedInAgent-TrendBot/0.1 (+https://github.com/ChanduKaranam/linkedin-agent)"
_MIN_MARKDOWN_LEN = 80   # lowered from 200 — many real articles are short


def _extract_domain(url: str) -> str:
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    return m.group(1).strip() if m else ""


async def scrape_url(url: str, timeout: int = 25) -> ScrapedPage | None:
    """Scrape a URL, returning clean markdown.
    Tries: 1) Crawl4AI (Playwright, JS-capable)
           2) httpx + trafilatura (static HTML)
           3) httpx + readability-lxml (fallback extractor)
    """
    # 1 — Crawl4AI (Playwright, handles JS-rendered pages)
    page = await _crawl4ai_scrape(url, timeout)
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


async def _crawl4ai_scrape(url: str, timeout: int) -> ScrapedPage | None:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        browser_cfg = BrowserConfig(headless=True, user_agent=_USER_AGENT, verbose=False)
        run_cfg = CrawlerRunConfig(page_timeout=timeout * 1000, verbose=False)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
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
    """Fetch HTML with httpx, then try trafilatura → readability in order."""
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

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
