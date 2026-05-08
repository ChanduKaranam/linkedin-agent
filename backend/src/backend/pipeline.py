from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import tldextract
from rapidfuzz import fuzz
from sqlalchemy.ext.asyncio import AsyncSession

from .agent.tools.robots import is_allowed, polite_delay
from .agent.tools.scrape import scrape_url
from .agent.tools.search import search_web
from .agent.trend_agent import synthesize_all, synthesize_daily
from .config import TopicConfig, get_settings
from .dedup import compute_fingerprint, deduplicate_urls
from .logging_setup import get_logger
from .models import Cluster, PersistedTrend, ScrapedPage, Source
from .rag.indexer import index_trend
from .storage import (
    create_run,
    fingerprint_exists_in_window,
    get_recent_headlines,
    get_stale_runs,
    run_exists_for_date,
    unique_slug,
    update_run_state,
    upsert_trend,
)

if TYPE_CHECKING:
    from crawl4ai import AsyncWebCrawler

log = get_logger(__name__)

# Track background indexing tasks so GC doesn't discard them before they finish
_bg_index_tasks: set[asyncio.Task] = set()


def _domain(url: str) -> str:
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain


async def _background_index(
    pending: list[tuple[int, str, list[Source]]],
    cache_dir: Path,
) -> None:
    """Index trends sequentially in a fresh session. Runs as a background task."""
    from .db import _get_factory
    try:
        async with _get_factory()() as session:
            for trend_id, run_id, sources in pending:
                try:
                    await index_trend(session, trend_id, run_id, sources, cache_dir)
                except Exception as exc:
                    log.exception("background_index_trend_failed", trend_id=trend_id, error=str(exc))
    except Exception as exc:
        log.exception("background_index_session_failed", error=str(exc))


def _fire_background_index(
    pending: list[tuple[int, str, list[Source]]],
    cache_dir: Path,
) -> None:
    """Schedule background indexing and track the task to prevent GC."""
    if not pending:
        return
    task = asyncio.create_task(_background_index(pending, cache_dir))
    _bg_index_tasks.add(task)
    task.add_done_callback(_bg_index_tasks.discard)


async def _open_shared_crawler():
    """Return (crawler, cleanup_coro) or (None, None) if Crawl4AI unavailable."""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        crawler = AsyncWebCrawler(config=browser_cfg)
        await crawler.__aenter__()
        return crawler
    except Exception as exc:
        log.warning("crawl4ai_unavailable_using_httpx_only", error=str(exc)[:120])
        return None


async def _close_shared_crawler(crawler) -> None:
    if crawler is None:
        return
    try:
        await crawler.__aexit__(None, None, None)
    except Exception:
        pass


async def run_pipeline(
    session: AsyncSession,
    run_id: str,
    run_date: date,
    topic_cfg: TopicConfig,
    cache_dir: Path,
) -> tuple[int, int]:
    """Run the 4-phase pipeline. Returns (trend_count, warning_count)."""
    limits = topic_cfg.limits

    # ── Phase 1: Discover ──────────────────────────────────────────────────
    await update_run_state(session, run_id, "discovering")
    log.info("phase_start", phase="discover", run_id=run_id)

    # Fetch all query results in parallel
    query_results = await asyncio.gather(
        *[search_web(q, max_results=limits.max_per_query) for q in topic_cfg.queries],
        return_exceptions=True,
    )

    all_urls: list[dict] = []
    seen_canon: set[str] = set()
    for result in query_results:
        if isinstance(result, Exception):
            log.warning("search_query_failed", error=str(result))
            continue
        for item in result:
            if not item.url:
                continue
            canon_list = deduplicate_urls([item.url])
            if not canon_list:
                continue
            canon = canon_list[0]
            dom = _domain(item.url)
            if topic_cfg.is_domain_blocked(dom):
                continue
            if canon in seen_canon:
                continue
            seen_canon.add(canon)
            all_urls.append({"url": item.url, "title": item.title, "snippet": item.snippet, "domain": dom})
            if len(all_urls) >= limits.max_sources_per_run:
                break
        if len(all_urls) >= limits.max_sources_per_run:
            break

    # robots.txt filter — parallel with bounded concurrency
    robots_sem = asyncio.Semaphore(8)

    async def _check_robots(item: dict) -> dict | None:
        async with robots_sem:
            try:
                if await is_allowed(item["url"], limits.per_domain_rps):
                    return item
            except Exception as exc:
                log.warning("robots_check_failed_disallowing", url=item["url"], error=str(exc))
            return None

    robots_results = await asyncio.gather(*[_check_robots(u) for u in all_urls])
    all_urls = [r for r in robots_results if r is not None]

    if not all_urls:
        await update_run_state(session, run_id, "failed", 0, 0, "NO_SOURCES")
        log.error("no_sources_found", run_id=run_id)
        raise RuntimeError("NO_SOURCES")

    log.info("discover_complete", url_count=len(all_urls), run_id=run_id)

    # ── Phase 2: Scrape ────────────────────────────────────────────────────
    await update_run_state(session, run_id, "scraping")
    await session.commit()  # release connection to pool during long scrape phase
    log.info("phase_start", phase="scrape", run_id=run_id, url_count=len(all_urls))

    sem = asyncio.Semaphore(limits.scrape_concurrency)
    crawler = await _open_shared_crawler()

    try:
        async def _scrape_one(item: dict) -> tuple[dict, ScrapedPage | None]:
            async with sem:
                await polite_delay(item["domain"], limits.per_domain_rps)
                cache_key = hashlib.md5(item["url"].encode()).hexdigest()
                cache_file = cache_dir / f"{cache_key}.md"
                if cache_file.exists():
                    age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
                    if age_hours <= limits.cache_ttl_hours:
                        markdown = cache_file.read_text(encoding="utf-8")
                        return item, ScrapedPage(
                            url=item["url"],
                            title=item["title"],
                            markdown=markdown,
                            domain=item["domain"],
                            scrape_method="cache",
                        )
                    cache_file.unlink(missing_ok=True)
                page = await scrape_url(item["url"], timeout=limits.scrape_timeout_seconds, crawler=crawler)
                if page:
                    # Truncate at the I/O boundary — synthesis only uses the first N chars
                    page.markdown = page.markdown[:limits.summarize_max_chars_per_source]
                    cache_file.write_text(page.markdown, encoding="utf-8")
                return item, page

        scrape_results = await asyncio.gather(*[_scrape_one(u) for u in all_urls], return_exceptions=True)
    finally:
        await _close_shared_crawler(crawler)

    scrape_warnings = 0
    scraped: list[tuple[dict, ScrapedPage]] = []
    for result in scrape_results:
        if isinstance(result, Exception):
            log.warning("scrape_exception", error=str(result))
            scrape_warnings += 1
            continue
        item, page = result
        if page:
            scraped.append((item, page))
        else:
            scrape_warnings += 1

    fail_rate = 1 - (len(scraped) / max(len(all_urls), 1))
    if fail_rate > 0.5:
        await update_run_state(session, run_id, "failed", 0, 0, "SCRAPE_MAJORITY_FAILED")
        raise RuntimeError("SCRAPE_MAJORITY_FAILED")

    log.info("scrape_complete", scraped=len(scraped), total=len(all_urls), run_id=run_id)

    # ── Phase 3: Daily Synthesis ───────────────────────────────────────────
    await update_run_state(session, run_id, "summarizing")
    await session.commit()  # release connection to pool during LLM call
    log.info("phase_start", phase="daily_synthesis", run_id=run_id, article_count=len(scraped))

    chars_per_article = min(limits.summarize_max_chars_per_source, 1200)
    capped_scraped = scraped[:25]
    content_parts = [
        f"# {page.title}\nSource: {page.url}\n\n{page.markdown[:chars_per_article]}"
        for item, page in capped_scraped
    ]
    all_sources = [
        Source(url=item["url"], title=item["title"] or item["domain"], domain=item["domain"])
        for item in all_urls
    ]

    try:
        daily_briefs = await synthesize_daily(content_parts, topic_cfg.topic, topic_cfg.models.summarize, run_date)
    except Exception as exc:
        await update_run_state(session, run_id, "failed", 0, 0, f"DAILY_SYNTHESIS_FAILED:{exc}")
        raise

    deduped_trends = _dedup_by_headline_similarity(daily_briefs.trends)
    log.info("daily_synthesis_complete", story_count=len(deduped_trends), run_id=run_id)

    # ── Phase 4: Persist (RAG indexing runs in background after state update) ──
    trend_count = 0
    warnings = scrape_warnings
    window = topic_cfg.dedup.cross_day_window
    settings = get_settings()
    recent_headlines = await get_recent_headlines(session, window)

    # Collect (trend_id, run_id, sources) for background indexing
    index_pending: list[tuple[int, str, list[Source]]] = []

    for summary in deduped_trends:
        fingerprint = compute_fingerprint(summary.headline)
        if await fingerprint_exists_in_window(session, fingerprint, window):
            log.info("trend_dedup_skipped", fingerprint=fingerprint[:8], headline=summary.headline)
            warnings += 1
            continue
        if any(fuzz.token_sort_ratio(summary.headline, h) >= 80 for h in recent_headlines):
            log.info("trend_fuzzy_dedup_skipped", headline=summary.headline)
            warnings += 1
            continue

        slug = await unique_slug(session, summary.headline, run_date)
        trend = PersistedTrend(
            run_id=run_id,
            run_date=run_date,
            slug=slug,
            headline=summary.headline,
            one_liner=summary.one_liner,
            detailed_markdown=summary.detailed_markdown,
            key_points=summary.key_points,
            sources=all_sources,
            fingerprint=fingerprint,
        )
        trend_id = await upsert_trend(session, trend)
        index_pending.append((trend_id, run_id, all_sources))
        trend_count += 1
        log.info("trend_persisted", slug=slug, headline=summary.headline, run_id=run_id)

    final_state = "completed" if warnings == 0 else "completed_with_warnings"
    await update_run_state(session, run_id, final_state, trend_count, warnings)

    # Fire RAG indexing in the background — does not block "completed" state
    _fire_background_index(index_pending, settings.cache_dir)

    log.info("pipeline_complete", run_id=run_id, trends=trend_count, warnings=warnings)
    return trend_count, warnings


def _dedup_by_headline_similarity(summaries: list, threshold: int = 80) -> list:
    kept = []
    for summary in summaries:
        if not any(fuzz.token_sort_ratio(summary.headline, k.headline) >= threshold for k in kept):
            kept.append(summary)
    return kept


def _rule_based_cluster(snippets: list[dict]) -> list[Cluster]:
    """Fallback: group by domain + title similarity."""
    clusters: list[list[int]] = []
    assigned: set[int] = set()
    for i, a in enumerate(snippets):
        if i in assigned:
            continue
        group = [i]
        assigned.add(i)
        for j, b in enumerate(snippets):
            if j in assigned:
                continue
            if a["domain"] == b["domain"] or fuzz.token_sort_ratio(a["title"], b["title"]) >= 70:
                group.append(j)
                assigned.add(j)
        clusters.append(group)
    return [Cluster(trend_id=f"cluster-{idx}", member_indices=m) for idx, m in enumerate(clusters)]


def build_adhoc_topic_config(topic_input: str, base: TopicConfig) -> TopicConfig:
    cleaned = topic_input.strip()
    queries = [cleaned, f"{cleaned} news", f"{cleaned} this week", f"{cleaned} latest updates"]
    settings = get_settings()
    adhoc_limits = base.limits.model_copy(
        update={
            "max_sources_per_run": min(base.limits.max_sources_per_run, settings.adhoc_max_sources_per_run),
            "max_per_query": min(base.limits.max_per_query, settings.adhoc_max_per_query),
            "scrape_concurrency": min(base.limits.scrape_concurrency, settings.adhoc_scrape_concurrency),
            "summarize_max_chars_per_source": min(
                base.limits.summarize_max_chars_per_source,
                settings.adhoc_summarize_max_chars_per_source,
            ),
        }
    )
    return base.model_copy(update={"topic": cleaned, "queries": queries, "limits": adhoc_limits})


async def _mark_failed_fresh(run_id: str, error: str) -> None:
    """Mark a run as failed using a fresh DB session.

    The main pipeline session may be in a corrupted/rollback-only state after an
    exception, so error handlers must not reuse it.  Opening a new session here
    ensures the state update always reaches the DB even when the pipeline session died.
    """
    from .db import _get_factory
    try:
        async with _get_factory()() as fresh_session:
            await update_run_state(fresh_session, run_id, "failed", 0, 0, error)
    except Exception as inner:
        log.error("failed_to_mark_run_failed", run_id=run_id, error=str(inner))


async def run_pipeline_safe(
    session: AsyncSession,
    run_id: str,
    run_date: date,
    topic_cfg: TopicConfig,
    cache_dir: Path,
) -> None:
    try:
        await run_pipeline(session, run_id, run_date, topic_cfg, cache_dir)
    except RuntimeError as exc:
        code = str(exc)
        # NO_SOURCES / SCRAPE_MAJORITY_FAILED already called update_run_state("failed")
        # inside run_pipeline before raising, so skip the double-update.
        if not any(code.startswith(c) for c in ("NO_SOURCES", "SCRAPE_MAJORITY_FAILED")):
            await _mark_failed_fresh(run_id, f"INTERNAL:{code}")
    except Exception as exc:
        log.exception("pipeline_uncaught_error", run_id=run_id, error=str(exc))
        await _mark_failed_fresh(run_id, f"INTERNAL:{exc}")


# ── Search synthesis pipeline ─────────────────────────────────────────────────

async def run_search_synthesis(
    session: AsyncSession,
    run_id: str,
    run_date: date,
    topic_cfg: TopicConfig,
    cache_dir: Path,
) -> tuple[int, int]:
    limits = topic_cfg.limits

    await update_run_state(session, run_id, "discovering")
    log.info("phase_start", phase="discover", run_id=run_id)

    # Fetch all query results in parallel
    query_results = await asyncio.gather(
        *[search_web(q, max_results=limits.max_per_query) for q in topic_cfg.queries],
        return_exceptions=True,
    )

    all_urls: list[dict] = []
    seen_canon: set[str] = set()
    for result in query_results:
        if isinstance(result, Exception):
            log.warning("search_query_failed", error=str(result))
            continue
        for item in result:
            if not item.url:
                continue
            canon_list = deduplicate_urls([item.url])
            if not canon_list:
                continue
            canon = canon_list[0]
            dom = _domain(item.url)
            if topic_cfg.is_domain_blocked(dom):
                continue
            if canon in seen_canon:
                continue
            seen_canon.add(canon)
            all_urls.append({"url": item.url, "title": item.title, "snippet": item.snippet, "domain": dom})
            if len(all_urls) >= limits.max_sources_per_run:
                break
        if len(all_urls) >= limits.max_sources_per_run:
            break

    # robots.txt filter — parallel with bounded concurrency
    robots_sem = asyncio.Semaphore(8)

    async def _check_robots(item: dict) -> dict | None:
        async with robots_sem:
            try:
                if await is_allowed(item["url"], limits.per_domain_rps):
                    return item
            except Exception as exc:
                log.warning("robots_check_failed_disallowing", url=item["url"], error=str(exc))
            return None

    robots_results = await asyncio.gather(*[_check_robots(u) for u in all_urls])
    all_urls = [r for r in robots_results if r is not None]

    if not all_urls:
        await update_run_state(session, run_id, "failed", 0, 0, "NO_SOURCES")
        raise RuntimeError("NO_SOURCES")

    log.info("discover_complete", url_count=len(all_urls), run_id=run_id)

    await update_run_state(session, run_id, "scraping")
    await session.commit()  # release connection during scrape
    log.info("phase_start", phase="scrape", run_id=run_id, url_count=len(all_urls))

    sem = asyncio.Semaphore(limits.scrape_concurrency)
    crawler = await _open_shared_crawler()

    try:
        async def _scrape_one(item: dict) -> tuple[dict, ScrapedPage | None]:
            async with sem:
                await polite_delay(item["domain"], limits.per_domain_rps)
                cache_key = hashlib.md5(item["url"].encode()).hexdigest()
                cache_file = cache_dir / f"{cache_key}.md"
                if cache_file.exists():
                    age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
                    if age_hours <= limits.cache_ttl_hours:
                        markdown = cache_file.read_text(encoding="utf-8")
                        return item, ScrapedPage(
                            url=item["url"],
                            title=item["title"],
                            markdown=markdown,
                            domain=item["domain"],
                            scrape_method="cache",
                        )
                    cache_file.unlink(missing_ok=True)
                page = await scrape_url(item["url"], timeout=limits.scrape_timeout_seconds, crawler=crawler)
                if page:
                    # Truncate at the I/O boundary before storing in memory and on disk
                    page.markdown = page.markdown[:limits.summarize_max_chars_per_source]
                    cache_file.write_text(page.markdown, encoding="utf-8")
                return item, page

        scrape_results = await asyncio.gather(*[_scrape_one(u) for u in all_urls], return_exceptions=True)
    finally:
        await _close_shared_crawler(crawler)

    scraped: list[tuple[dict, ScrapedPage]] = []
    for result in scrape_results:
        if isinstance(result, Exception):
            log.warning("scrape_exception", error=str(result))
            continue
        item, page = result
        if page:
            scraped.append((item, page))

    fail_rate = 1 - (len(scraped) / max(len(all_urls), 1))
    if fail_rate > 0.5:
        await update_run_state(session, run_id, "failed", 0, 0, "SCRAPE_MAJORITY_FAILED")
        raise RuntimeError("SCRAPE_MAJORITY_FAILED")

    log.info("scrape_complete", scraped=len(scraped), total=len(all_urls), run_id=run_id)

    await update_run_state(session, run_id, "summarizing")
    await session.commit()  # release connection during LLM synthesis call
    log.info("phase_start", phase="synthesize", run_id=run_id, source_count=len(scraped))

    content_parts = [
        f"# {page.title}\nSource: {page.url}\n\n{page.markdown[:limits.summarize_max_chars_per_source]}"
        for item, page in scraped
    ]
    scraped_urls = {page.url for _, page in scraped}
    for item in all_urls:
        if item["url"] not in scraped_urls and item.get("snippet"):
            content_parts.append(f"# {item['title']}\nSource: {item['url']}\n\n{item['snippet']}")

    sources = [
        Source(url=item["url"], title=item["title"] or item["domain"], domain=item["domain"])
        for item in all_urls
    ]

    try:
        summary = await synthesize_all(content_parts, topic_cfg.topic, topic_cfg.models.summarize)
    except Exception as exc:
        await update_run_state(session, run_id, "failed", 0, 0, f"SYNTHESIS_FAILED:{exc}")
        raise

    fingerprint = compute_fingerprint(summary.headline)
    slug = await unique_slug(session, summary.headline, run_date)

    trend = PersistedTrend(
        run_id=run_id,
        run_date=run_date,
        slug=slug,
        headline=summary.headline,
        one_liner=summary.one_liner,
        detailed_markdown=summary.detailed_markdown,
        key_points=summary.key_points,
        sources=sources,
        fingerprint=fingerprint,
    )
    trend_id = await upsert_trend(session, trend)

    # Mark completed before indexing — user sees results immediately
    await update_run_state(session, run_id, "completed", 1, 0)
    log.info("synthesis_pipeline_complete", run_id=run_id, headline=summary.headline)

    # RAG indexing runs in the background
    _fire_background_index([(trend_id, run_id, sources)], get_settings().cache_dir)

    return 1, 0


async def run_search_synthesis_safe(
    session: AsyncSession,
    run_id: str,
    run_date: date,
    topic_cfg: TopicConfig,
    cache_dir: Path,
) -> None:
    try:
        await run_search_synthesis(session, run_id, run_date, topic_cfg, cache_dir)
    except RuntimeError as exc:
        code = str(exc)
        if not any(code.startswith(c) for c in ("NO_SOURCES", "SCRAPE_MAJORITY_FAILED", "SYNTHESIS_FAILED")):
            await update_run_state(session, run_id, "failed", 0, 0, f"INTERNAL:{code}")
    except Exception as exc:
        log.exception("synthesis_pipeline_uncaught_error", run_id=run_id, error=str(exc))
        await update_run_state(session, run_id, "failed", 0, 0, f"INTERNAL:{exc}")
