from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from backend.models import PersistedTrend, Source
from backend.storage import (
    create_run,
    get_run,
    get_trends_for_date,
    list_runs,
    run_exists_for_date,
    update_run_state,
    upsert_trend,
)


def _make_trend(run_id: str, run_date: date, slug: str = "test-trend", fp: str = "abc123") -> PersistedTrend:
    return PersistedTrend(
        run_id=run_id,
        run_date=run_date,
        slug=slug,
        headline="Test Headline",
        one_liner="A one-liner summary.",
        detailed_markdown="## Details\n\nSome detail text.",
        key_points=["Point A", "Point B"],
        sources=[Source(url="https://example.com/1", title="Example", domain="example.com")],
        fingerprint=fp,
    )


def test_create_and_get_run(tmp_db: Path) -> None:
    create_run(tmp_db, "run-1", date(2026, 4, 24), "AI & tech")
    run = get_run(tmp_db, "run-1")
    assert run is not None
    assert run.state == "pending"
    assert run.topic == "AI & tech"


def test_update_run_state(tmp_db: Path) -> None:
    create_run(tmp_db, "run-2", date(2026, 4, 24), "AI & tech")
    update_run_state(tmp_db, "run-2", "completed", trend_count=5, warnings=0)
    run = get_run(tmp_db, "run-2")
    assert run.state == "completed"
    assert run.trend_count == 5
    assert run.finished_at is not None


def test_run_exists_for_date(tmp_db: Path) -> None:
    create_run(tmp_db, "run-3", date(2026, 4, 25), "AI & tech")
    assert run_exists_for_date(tmp_db, date(2026, 4, 25), "AI & tech")
    assert not run_exists_for_date(tmp_db, date(2026, 4, 26), "AI & tech")


def test_upsert_trend_and_retrieve(tmp_db: Path) -> None:
    create_run(tmp_db, "run-4", date(2026, 4, 24), "AI & tech")
    trend = _make_trend("run-4", date(2026, 4, 24))
    upsert_trend(tmp_db, trend)

    trends = get_trends_for_date(tmp_db, date(2026, 4, 24))
    assert len(trends) == 1
    assert trends[0].headline == "Test Headline"
    assert trends[0].key_points == ["Point A", "Point B"]


def test_upsert_trend_dedup_increments_seen_again(tmp_db: Path) -> None:
    create_run(tmp_db, "run-5", date(2026, 4, 24), "AI & tech")
    trend = _make_trend("run-5", date(2026, 4, 24), fp="unique-fp-xyz")
    upsert_trend(tmp_db, trend)

    # Second upsert same fingerprint — should increment seen_again, not create new row
    trend2 = _make_trend("run-5", date(2026, 4, 24), slug="test-trend-2", fp="unique-fp-xyz")
    upsert_trend(tmp_db, trend2)

    trends = get_trends_for_date(tmp_db, date(2026, 4, 24))
    # Still only one persisted row (dedup active); seen_again incremented
    assert len(trends) == 1


def test_list_runs(tmp_db: Path) -> None:
    for i in range(3):
        create_run(tmp_db, f"run-list-{i}", date(2026, 4, i + 1), "AI & tech")
    runs = list_runs(tmp_db, limit=10)
    assert len(runs) == 3


def test_schema_migrations_idempotent(tmp_db: Path) -> None:
    from backend.storage import init_db
    init_db(tmp_db)  # second call — should not raise
    init_db(tmp_db)  # third call
