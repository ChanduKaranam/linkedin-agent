from __future__ import annotations

import asyncio
import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

import tldextract
from rapidfuzz import fuzz
from slugify import slugify

from .agent.tools.robots import is_allowed, polite_delay
from .agent.tools.scrape import scrape_url
from .agent.tools.search import search_web
from .agent.trend_agent import cluster_articles, summarize_cluster, synthesize_all, synthesize_daily
from .config import Limits, TopicConfig, get_settings
from .dedup import compute_fingerprint, deduplicate_urls
from .logging_setup import get_logger
from .models import Cluster, PersistedTrend, ScrapedPage, Source
from .storage import (
    create_run,
    fingerprint_exists_in_window,
    get_stale_runs,
    run_exists_for_date,
    update_run_state,
    upsert_trend,
)

log = get_logger(__name__)


def _domain(url: str) -> str:
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain


async def run_pipeline(
    run_id: str,
    run_date: date,
    topic_cfg: TopicConfig,
    db_path: Path,
    cache_dir: Path,
) -> tuple[int, int]:
    """Run the 4-phase pipeline. Returns (trend_count, warning_count)."""
    limits = topic_cfg.limits

    # ── Phase 1: Discover ──────────────────────────────────────────────────
    update_run_state(db_path, run_id, "discovering")
    log.info("phase_start", phase="discover", run_id=run_id)

    all_urls: list[dict] = []
    seen_canon: set[str] = set()

    for query in topic_cfg.queries:
        discovered = await search_web(query, max_results=limits.max_per_query)
        for item in discovered:
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

    # robots.txt filter
    allowed: list[dict] = []
    for item in all_urls:
        try:
            if await is_allowed(item["url"], limits.per_domain_rps):
                allowed.append(item)
        except Exception:
            allowed.append(item)
    all_urls = allowed

    if not all_urls:
        update_run_state(db_path, run_id, "failed", 0, 0, "NO_SOURCES")
        log.error("no_sources_found", run_id=run_id)
        raise RuntimeError("NO_SOURCES")

    log.info("discover_complete", url_count=len(all_urls), run_id=run_id)

    # ── Phase 2: Scrape ────────────────────────────────────────────────────
    update_run_state(db_path, run_id, "scraping")
    log.info("phase_start", phase="scrape", run_id=run_id, url_count=len(all_urls))

    sem = asyncio.Semaphore(limits.scrape_concurrency)

    async def _scrape_one(item: dict) -> tuple[dict, ScrapedPage | None]:
        async with sem:
            await polite_delay(item["domain"], limits.per_domain_rps)
            cache_key = hashlib.md5(item["url"].encode()).hexdigest()
            cache_file = cache_dir / f"{cache_key}.md"
            if cache_file.exists():
                markdown = cache_file.read_text(encoding="utf-8")
                return item, ScrapedPage(
                    url=item["url"],
                    title=item["title"],
                    markdown=markdown,
                    domain=item["domain"],
                    scrape_method="cache",
                )
            page = await scrape_url(item["url"], timeout=limits.scrape_timeout_seconds)
            if page:
                cache_file.write_text(page.markdown, encoding="utf-8")
            return item, page

    scrape_results = await asyncio.gather(*[_scrape_one(u) for u in all_urls], return_exceptions=True)

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
        update_run_state(db_path, run_id, "failed", 0, 0, "SCRAPE_MAJORITY_FAILED")
        raise RuntimeError("SCRAPE_MAJORITY_FAILED")

    log.info("scrape_complete", scraped=len(scraped), total=len(all_urls), run_id=run_id)

    # ── Phase 3: Daily Synthesis (one LLM call → distinct story briefs) ──
    # Replaces the old cluster + per-cluster summarize approach.
    # The LLM reads ALL content and decides what the distinct stories are,
    # preventing multiple headlines for the same event.
    update_run_state(db_path, run_id, "summarizing")
    log.info("phase_start", phase="daily_synthesis", run_id=run_id, article_count=len(scraped))

    # Trim each article to stay within the model's context window.
    # Cap at 25 articles × 1200 chars ≈ 9k tokens — well within mistral-large (128k context).
    # Prioritise successfully scraped pages (full content) over snippet-only fallbacks.
    chars_per_article = min(limits.summarize_max_chars_per_source, 1200)
    capped_scraped = scraped[:25]  # Hard cap: never feed more than 25 articles at once
    content_parts = [
        f"# {page.title}\nSource: {page.url}\n\n{page.markdown[:chars_per_article]}"
        for item, page in capped_scraped
    ]
    # All discovered URLs as sources regardless of scrape success
    all_sources = [
        Source(url=item["url"], title=item["title"] or item["domain"], domain=item["domain"])
        for item in all_urls
    ]

    try:
        daily_briefs = await synthesize_daily(content_parts, topic_cfg.topic, topic_cfg.models.summarize, run_date)
    except Exception as exc:
        update_run_state(db_path, run_id, "failed", 0, 0, f"DAILY_SYNTHESIS_FAILED:{exc}")
        raise

    deduped_trends = _dedup_by_headline_similarity(daily_briefs.trends)
    if len(deduped_trends) < len(daily_briefs.trends):
        log.info("headline_similarity_dedup", before=len(daily_briefs.trends), after=len(deduped_trends), run_id=run_id)
    log.info("daily_synthesis_complete", story_count=len(deduped_trends), run_id=run_id)

    trend_count = 0
    warnings = 0
    window = topic_cfg.dedup.cross_day_window

    for summary in deduped_trends:
        fingerprint = compute_fingerprint(summary.headline, all_sources)
        if fingerprint_exists_in_window(db_path, fingerprint, window):
            log.info("trend_dedup_skipped", fingerprint=fingerprint[:8], headline=summary.headline)
            continue

        slug = _unique_slug(summary.headline, run_date, db_path)
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
        upsert_trend(db_path, trend)
        trend_count += 1
        log.info("trend_persisted", slug=slug, headline=summary.headline, run_id=run_id)

    final_state = "completed" if warnings == 0 else "completed_with_warnings"
    update_run_state(db_path, run_id, final_state, trend_count, warnings)
    log.info("pipeline_complete", run_id=run_id, trends=trend_count, warnings=warnings, state=final_state)
    return trend_count, warnings


def _dedup_by_headline_similarity(summaries: list, threshold: int = 80) -> list:
    """Remove near-duplicate trends where headlines are too similar (LLM may produce subtle variants)."""
    kept = []
    for summary in summaries:
        if not any(fuzz.token_sort_ratio(summary.headline, k.headline) >= threshold for k in kept):
            kept.append(summary)
    return kept


def _rule_based_cluster(snippets: list[dict]) -> list[Cluster]:
    """Fallback: group by domain + title similarity (rapidfuzz)."""
    clusters: list[list[int]] = []
    assigned = set()

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

    return [
        Cluster(
            trend_id=f"cluster-{idx}",
            member_indices=members,
        )
        for idx, members in enumerate(clusters)
    ]


def _unique_slug(headline: str, run_date: date, db_path: Path) -> str:
    base = slugify(headline)[:80]
    slug = base
    n = 1
    from .storage import _conn
    with _conn(db_path) as con:
        while con.execute(
            "SELECT 1 FROM trends WHERE run_date=? AND slug=?",
            (run_date.isoformat(), slug)
        ).fetchone():
            slug = f"{base}-{n}"
            n += 1
    return slug


def build_adhoc_topic_config(topic_input: str, base: TopicConfig) -> TopicConfig:
    """Build a TopicConfig for an ad-hoc user search with boilerplate query expansion."""
    cleaned = topic_input.strip()
    queries = [
        cleaned,
        f"{cleaned} news",
        f"{cleaned} this week",
        f"{cleaned} latest updates",
    ]
    adhoc_limits = base.limits.model_copy(update={
        "max_sources_per_run": 15,
        "max_per_query": 5,
    })
    return base.model_copy(update={
        "topic": cleaned,
        "queries": queries,
        "limits": adhoc_limits,
    })


async def run_pipeline_safe(
    run_id: str,
    run_date: date,
    topic_cfg: TopicConfig,
    db_path: Path,
    cache_dir: Path,
) -> None:
    """Entry point that handles all errors and writes final state."""
    try:
        await run_pipeline(run_id, run_date, topic_cfg, db_path, cache_dir)
    except RuntimeError as exc:
        code = str(exc)
        if not any(code.startswith(c) for c in ("NO_SOURCES", "SCRAPE_MAJORITY_FAILED")):
            update_run_state(db_path, run_id, "failed", 0, 0, f"INTERNAL:{code}")
    except Exception as exc:
        log.exception("pipeline_uncaught_error", run_id=run_id, error=str(exc))
        update_run_state(db_path, run_id, "failed", 0, 0, f"INTERNAL:{exc}")


# ── Search synthesis pipeline ─────────────────────────────────────────────────

async def run_search_synthesis(
    run_id: str,
    run_date: date,
    topic_cfg: TopicConfig,
    db_path: Path,
    cache_dir: Path,
) -> tuple[int, int]:
    """Search pipeline: discover → scrape → synthesize_all (no clustering).
    Returns one comprehensive TrendSummary for the whole topic."""
    limits = topic_cfg.limits

    # ── Phase 1: Discover ──────────────────────────────────────────────────
    update_run_state(db_path, run_id, "discovering")
    log.info("phase_start", phase="discover", run_id=run_id)

    all_urls: list[dict] = []
    seen_canon: set[str] = set()

    for query in topic_cfg.queries:
        discovered = await search_web(query, max_results=limits.max_per_query)
        for item in discovered:
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

    # robots.txt filter
    allowed: list[dict] = []
    for item in all_urls:
        try:
            if await is_allowed(item["url"], limits.per_domain_rps):
                allowed.append(item)
        except Exception:
            allowed.append(item)
    all_urls = allowed

    if not all_urls:
        update_run_state(db_path, run_id, "failed", 0, 0, "NO_SOURCES")
        raise RuntimeError("NO_SOURCES")

    log.info("discover_complete", url_count=len(all_urls), run_id=run_id)

    # ── Phase 2: Scrape ────────────────────────────────────────────────────
    update_run_state(db_path, run_id, "scraping")
    log.info("phase_start", phase="scrape", run_id=run_id, url_count=len(all_urls))

    sem = asyncio.Semaphore(limits.scrape_concurrency)

    async def _scrape_one(item: dict) -> tuple[dict, ScrapedPage | None]:
        async with sem:
            await polite_delay(item["domain"], limits.per_domain_rps)
            cache_key = hashlib.md5(item["url"].encode()).hexdigest()
            cache_file = cache_dir / f"{cache_key}.md"
            if cache_file.exists():
                markdown = cache_file.read_text(encoding="utf-8")
                return item, ScrapedPage(
                    url=item["url"],
                    title=item["title"],
                    markdown=markdown,
                    domain=item["domain"],
                    scrape_method="cache",
                )
            page = await scrape_url(item["url"], timeout=limits.scrape_timeout_seconds)
            if page:
                cache_file.write_text(page.markdown, encoding="utf-8")
            return item, page

    scrape_results = await asyncio.gather(*[_scrape_one(u) for u in all_urls], return_exceptions=True)

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
        update_run_state(db_path, run_id, "failed", 0, 0, "SCRAPE_MAJORITY_FAILED")
        raise RuntimeError("SCRAPE_MAJORITY_FAILED")

    log.info("scrape_complete", scraped=len(scraped), total=len(all_urls), run_id=run_id)

    # ── Phase 3: Synthesize (single LLM call, no clustering) ──────────────
    update_run_state(db_path, run_id, "summarizing")
    log.info("phase_start", phase="synthesize", run_id=run_id, source_count=len(scraped))

    # LLM content: only successfully scraped pages (quality content)
    content_parts = [
        f"# {page.title}\nSource: {page.url}\n\n{page.markdown[:limits.summarize_max_chars_per_source]}"
        for item, page in scraped
    ]

    # For pages that failed to scrape, use the search snippet as minimal content
    scraped_urls = {page.url for _, page in scraped}
    for item in all_urls:
        if item["url"] not in scraped_urls and item.get("snippet"):
            content_parts.append(
                f"# {item['title']}\nSource: {item['url']}\n\n{item['snippet']}"
            )

    # Sources: ALL discovered URLs — every researched page gets credited
    sources = [
        Source(url=item["url"], title=item["title"] or item["domain"], domain=item["domain"])
        for item in all_urls
    ]

    try:
        summary = await synthesize_all(content_parts, topic_cfg.topic, topic_cfg.models.summarize)
    except Exception as exc:
        update_run_state(db_path, run_id, "failed", 0, 0, f"SYNTHESIS_FAILED:{exc}")
        raise

    fingerprint = compute_fingerprint(summary.headline, sources)
    slug = _unique_slug(summary.headline, run_date, db_path)

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
    upsert_trend(db_path, trend)

    update_run_state(db_path, run_id, "completed", 1, 0)
    log.info("synthesis_pipeline_complete", run_id=run_id, headline=summary.headline)
    return 1, 0


async def run_search_synthesis_safe(
    run_id: str,
    run_date: date,
    topic_cfg: TopicConfig,
    db_path: Path,
    cache_dir: Path,
) -> None:
    """Error-handling wrapper for run_search_synthesis."""
    try:
        await run_search_synthesis(run_id, run_date, topic_cfg, db_path, cache_dir)
    except RuntimeError as exc:
        code = str(exc)
        if not any(code.startswith(c) for c in ("NO_SOURCES", "SCRAPE_MAJORITY_FAILED", "SYNTHESIS_FAILED")):
            update_run_state(db_path, run_id, "failed", 0, 0, f"INTERNAL:{code}")
    except Exception as exc:
        log.exception("synthesis_pipeline_uncaught_error", run_id=run_id, error=str(exc))
        update_run_state(db_path, run_id, "failed", 0, 0, f"INTERNAL:{exc}")
