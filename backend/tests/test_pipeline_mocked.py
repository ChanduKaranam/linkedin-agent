from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import Cluster, ScrapedPage, TrendSummary
from backend.storage import get_run, get_trends_for_date, create_run
from tests.conftest import FIXTURE_MARKDOWN, FIXTURE_MARKDOWN_2

FAKE_SEARCH = [
    MagicMock(url="https://a.com/1", title="GPT-5 Release", snippet="OpenAI releases GPT-5", source_query="ai"),
    MagicMock(url="https://b.com/1", title="AlphaFold Update", snippet="DeepMind AlphaFold news", source_query="ai"),
    MagicMock(url="https://c.com/1", title="GPT-5 Details", snippet="More on GPT-5", source_query="ai"),
]

FAKE_PAGES = {
    "https://a.com/1": ScrapedPage(url="https://a.com/1", title="GPT-5 Release", markdown=FIXTURE_MARKDOWN, domain="a.com"),
    "https://b.com/1": ScrapedPage(url="https://b.com/1", title="AlphaFold Update", markdown=FIXTURE_MARKDOWN_2, domain="b.com"),
    "https://c.com/1": ScrapedPage(url="https://c.com/1", title="GPT-5 Details", markdown=FIXTURE_MARKDOWN, domain="c.com"),
}

FAKE_CLUSTERS = [
    Cluster(trend_id="gpt5-release", member_indices=[0, 2]),
    Cluster(trend_id="alphafold-update", member_indices=[1]),
]

FAKE_SUMMARY = TrendSummary(
    headline="OpenAI Releases GPT-5 with Breakthrough Reasoning",
    one_liner="OpenAI's GPT-5 sets new benchmarks in multi-step reasoning and code generation.",
    detailed_markdown="## What Happened\n\nOpenAI launched GPT-5...\n\n## Why It Matters\n\nThis is a significant leap.",
    key_points=["40% better on MMLU", "200k context window", "Native tool use"],
)


@pytest.mark.asyncio
async def test_pipeline_end_to_end_mocked(tmp_db: Path, tmp_cache: Path) -> None:
    from backend.config import TopicConfig, Limits, Models, Dedup
    from backend.pipeline import run_pipeline

    topic_cfg = TopicConfig(
        topic="AI & tech",
        queries=["ai news"],
        limits=Limits(max_sources_per_run=10, max_per_query=5, scrape_concurrency=2),
        models=Models(cluster="mistral/mistral-small-latest", summarize="mistral/mistral-small-latest"),
        dedup=Dedup(cross_day_window=3),
    )

    run_id = "test-run-001"
    run_date = date(2026, 4, 24)
    create_run(tmp_db, run_id, run_date, topic_cfg.topic)

    async def fake_search(query, max_results=10):
        return FAKE_SEARCH

    async def fake_scrape(url, timeout=25):
        return FAKE_PAGES.get(url)

    async def fake_is_allowed(url, rps=0.5):
        return True

    async def fake_polite_delay(domain, rps=0.5):
        pass

    async def fake_cluster(snippets, topic, model):
        return FAKE_CLUSTERS

    async def fake_summarize(trend_id, content_parts, topic, model):
        return FAKE_SUMMARY

    with (
        patch("backend.pipeline.search_web", side_effect=fake_search),
        patch("backend.pipeline.scrape_url", side_effect=fake_scrape),
        patch("backend.pipeline.is_allowed", side_effect=fake_is_allowed),
        patch("backend.pipeline.polite_delay", side_effect=fake_polite_delay),
        patch("backend.pipeline.cluster_articles", side_effect=fake_cluster),
        patch("backend.pipeline.summarize_cluster", side_effect=fake_summarize),
    ):
        trend_count, warnings = await run_pipeline(run_id, run_date, topic_cfg, tmp_db, tmp_cache)

    assert trend_count >= 1
    assert warnings == 0

    run = get_run(tmp_db, run_id)
    assert run.state in ("completed", "completed_with_warnings")
    assert run.trend_count >= 1

    trends = get_trends_for_date(tmp_db, run_date)
    assert len(trends) >= 1
    assert trends[0].headline == FAKE_SUMMARY.headline
    assert len(trends[0].key_points) == 3


@pytest.mark.asyncio
async def test_pipeline_no_sources_fails(tmp_db: Path, tmp_cache: Path) -> None:
    from backend.config import TopicConfig, Limits, Models, Dedup
    from backend.pipeline import run_pipeline

    topic_cfg = TopicConfig(
        topic="AI & tech",
        queries=["impossible query zzzz"],
        limits=Limits(),
        models=Models(),
        dedup=Dedup(),
    )
    run_id = "test-run-002"
    create_run(tmp_db, run_id, date(2026, 4, 25), topic_cfg.topic)

    async def fake_search(query, max_results=10):
        return []

    with patch("backend.pipeline.search_web", side_effect=fake_search):
        with pytest.raises(RuntimeError, match="NO_SOURCES"):
            await run_pipeline(run_id, date(2026, 4, 25), topic_cfg, tmp_db, tmp_cache)

    run = get_run(tmp_db, run_id)
    assert run.state == "failed"
    assert "NO_SOURCES" in (run.last_error or "")
