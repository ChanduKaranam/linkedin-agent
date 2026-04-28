from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Generator

from .models import PersistedTrend, RunState, Source

_SCHEMA_VERSION = 3

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    run_date    TEXT NOT NULL,
    topic       TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'daily',
    state       TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    trend_count INTEGER NOT NULL DEFAULT 0,
    warnings    INTEGER NOT NULL DEFAULT 0,
    last_error  TEXT,
    UNIQUE(run_date, topic)
);

CREATE INDEX IF NOT EXISTS idx_runs_kind_topic_date ON runs(kind, topic, run_date);

CREATE TABLE IF NOT EXISTS trends (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id             TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    run_date           TEXT NOT NULL,
    slug               TEXT NOT NULL,
    headline           TEXT NOT NULL,
    one_liner          TEXT NOT NULL,
    detailed_markdown  TEXT NOT NULL,
    key_points_json    TEXT NOT NULL,
    sources_json       TEXT NOT NULL,
    fingerprint        TEXT NOT NULL,
    seen_again         INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL,
    UNIQUE(run_date, slug)
);

CREATE INDEX IF NOT EXISTS idx_trends_run_date    ON trends(run_date);
CREATE INDEX IF NOT EXISTS idx_trends_fingerprint ON trends(fingerprint);

CREATE TABLE IF NOT EXISTS chat_messages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT NOT NULL,
    run_date       TEXT NOT NULL,
    slug           TEXT NOT NULL,
    role           TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content        TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    used_web       INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_date_slug ON chat_messages(run_date, slug, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_run_slug  ON chat_messages(run_id, slug, created_at);

CREATE TABLE IF NOT EXISTS insights (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL,
    run_date         TEXT NOT NULL,
    slug             TEXT NOT NULL,
    user_perspective TEXT NOT NULL,
    summary          TEXT NOT NULL DEFAULT '',
    tags_json        TEXT NOT NULL DEFAULT '[]',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_insights_date_slug ON insights(run_date, slug);
CREATE INDEX IF NOT EXISTS idx_insights_run_slug  ON insights(run_id, slug);
"""


@contextmanager
def _conn(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    con = sqlite3.connect(str(db_path), timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def init_db(db_path: Path) -> None:
    with _conn(db_path) as con:
        con.executescript(_DDL)
        cur = con.execute("SELECT version FROM schema_version LIMIT 1")
        row = cur.fetchone()
        if row is None:
            con.execute("INSERT INTO schema_version VALUES (?)", (_SCHEMA_VERSION,))
            con.commit()
        elif row["version"] < _SCHEMA_VERSION:
            _run_migrations(con, from_version=row["version"])
            con.execute("UPDATE schema_version SET version=?", (_SCHEMA_VERSION,))
            con.commit()


def _run_migrations(con: sqlite3.Connection, from_version: int) -> None:
    if from_version < 2:
        try:
            con.execute("ALTER TABLE runs ADD COLUMN kind TEXT NOT NULL DEFAULT 'daily'")
        except sqlite3.OperationalError:
            pass
        try:
            con.execute("CREATE INDEX IF NOT EXISTS idx_runs_kind_topic_date ON runs(kind, topic, run_date)")
        except sqlite3.OperationalError:
            pass
    if from_version < 3:
        for stmt in [
            """CREATE TABLE IF NOT EXISTS chat_messages (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id         TEXT NOT NULL,
                run_date       TEXT NOT NULL,
                slug           TEXT NOT NULL,
                role           TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content        TEXT NOT NULL,
                citations_json TEXT NOT NULL DEFAULT '[]',
                used_web       INTEGER NOT NULL DEFAULT 0,
                created_at     TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_chat_date_slug ON chat_messages(run_date, slug, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_chat_run_slug  ON chat_messages(run_id, slug, created_at)",
            """CREATE TABLE IF NOT EXISTS insights (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id           TEXT NOT NULL,
                run_date         TEXT NOT NULL,
                slug             TEXT NOT NULL,
                user_perspective TEXT NOT NULL,
                summary          TEXT NOT NULL DEFAULT '',
                tags_json        TEXT NOT NULL DEFAULT '[]',
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_insights_date_slug ON insights(run_date, slug)",
            "CREATE INDEX IF NOT EXISTS idx_insights_run_slug  ON insights(run_id, slug)",
        ]:
            try:
                con.execute(stmt)
            except sqlite3.OperationalError:
                pass


# ── Runs ──────────────────────────────────────────────────────────────────────

def create_run(db_path: Path, run_id: str, run_date: date, topic: str, kind: str = "daily") -> None:
    with _conn(db_path) as con:
        # Explicitly clear any existing row with the same (run_date, topic).
        # This handles stale / crashed runs without relying on INSERT OR REPLACE
        # conflict semantics, which can behave unexpectedly with WAL + FK pragmas.
        con.execute(
            "DELETE FROM runs WHERE run_date=? AND topic=?",
            (run_date.isoformat(), topic),
        )
        con.execute(
            """INSERT INTO runs
               (run_id, run_date, topic, kind, state, started_at)
               VALUES (?,?,?,?,?,?)""",
            (run_id, run_date.isoformat(), topic, kind, "pending", datetime.utcnow().isoformat()),
        )
        con.commit()


def find_adhoc_run(db_path: Path, topic: str, run_date: date) -> RunState | None:
    """Return the latest non-failed adhoc run for this topic on run_date, or None.
    Skips failed/interrupted runs so they don't block fresh searches.
    """
    with _conn(db_path) as con:
        row = con.execute(
            """SELECT * FROM runs
               WHERE kind='adhoc' AND topic=? AND run_date=? AND state != 'failed'
               ORDER BY started_at DESC LIMIT 1""",
            (topic, run_date.isoformat()),
        ).fetchone()
    return _row_to_run(row) if row else None


def update_run_state(
    db_path: Path,
    run_id: str,
    state: str,
    trend_count: int | None = None,
    warnings: int | None = None,
    last_error: str | None = None,
) -> None:
    finished_at = datetime.utcnow().isoformat() if state in ("completed", "failed", "completed_with_warnings") else None
    with _conn(db_path) as con:
        if trend_count is not None and warnings is not None:
            con.execute(
                """UPDATE runs SET state=?, finished_at=?, trend_count=?, warnings=?, last_error=?
                   WHERE run_id=?""",
                (state, finished_at, trend_count, warnings, last_error, run_id),
            )
        else:
            con.execute(
                "UPDATE runs SET state=?, finished_at=?, last_error=? WHERE run_id=?",
                (state, finished_at, last_error, run_id),
            )
        con.commit()


def get_run(db_path: Path, run_id: str) -> RunState | None:
    with _conn(db_path) as con:
        row = con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    return _row_to_run(row) if row else None


def get_latest_completed_run(db_path: Path) -> RunState | None:
    with _conn(db_path) as con:
        row = con.execute(
            """SELECT * FROM runs
               WHERE kind='daily' AND state IN ('completed','completed_with_warnings')
               ORDER BY run_date DESC LIMIT 1"""
        ).fetchone()
    return _row_to_run(row) if row else None


def get_stale_runs(db_path: Path) -> list[RunState]:
    """Runs that were left in-progress (agent crashed)."""
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT * FROM runs WHERE state NOT IN ('completed','completed_with_warnings','failed')"
        ).fetchall()
    return [_row_to_run(r) for r in rows]


def list_runs(db_path: Path, limit: int = 20) -> list[RunState]:
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_run(r) for r in rows]


def list_adhoc_runs(db_path: Path, limit: int = 50) -> list[RunState]:
    """Return completed adhoc (search) runs newest-first, stripping force suffixes."""
    with _conn(db_path) as con:
        rows = con.execute(
            """SELECT * FROM runs
               WHERE kind='adhoc' AND state IN ('completed','completed_with_warnings')
               ORDER BY started_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [_row_to_run(r) for r in rows]


def run_exists_for_date(db_path: Path, run_date: date, topic: str) -> bool:
    with _conn(db_path) as con:
        row = con.execute(
            "SELECT 1 FROM runs WHERE run_date=? AND topic=? AND state NOT IN ('failed')",
            (run_date.isoformat(), topic),
        ).fetchone()
    return row is not None


def _row_to_run(row: sqlite3.Row) -> RunState:
    keys = row.keys()
    return RunState(
        run_id=row["run_id"],
        run_date=date.fromisoformat(row["run_date"]),
        topic=row["topic"],
        kind=row["kind"] if "kind" in keys else "daily",
        state=row["state"],
        started_at=datetime.fromisoformat(row["started_at"]),
        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        trend_count=row["trend_count"],
        warnings=row["warnings"],
        last_error=row["last_error"],
    )


# ── Trends ────────────────────────────────────────────────────────────────────

def upsert_trend(db_path: Path, trend: PersistedTrend) -> None:
    """Insert or (if fingerprint duplicate) increment seen_again on existing row."""
    with _conn(db_path) as con:
        existing = con.execute(
            "SELECT id FROM trends WHERE fingerprint=? AND run_date >= date('now', ?)",
            (trend.fingerprint, f"-{_window_placeholder(db_path)} days"),
        ).fetchone()
        if existing:
            con.execute("UPDATE trends SET seen_again=seen_again+1 WHERE id=?", (existing["id"],))
        else:
            con.execute(
                """INSERT OR IGNORE INTO trends
                   (run_id, run_date, slug, headline, one_liner, detailed_markdown,
                    key_points_json, sources_json, fingerprint, seen_again, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,0,?)""",
                (
                    trend.run_id,
                    trend.run_date.isoformat(),
                    trend.slug,
                    trend.headline,
                    trend.one_liner,
                    trend.detailed_markdown,
                    json.dumps(trend.key_points),
                    json.dumps([s.model_dump() for s in trend.sources]),
                    trend.fingerprint,
                    datetime.utcnow().isoformat(),
                ),
            )
        con.commit()


def _window_placeholder(db_path: Path) -> int:
    """Import-safe way to get cross_day_window without circular imports."""
    try:
        from .config import get_topic_config
        return get_topic_config().dedup.cross_day_window
    except Exception:
        return 3


def get_trends_for_run(db_path: Path, run_id: str) -> list[PersistedTrend]:
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT * FROM trends WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
    return [_row_to_trend(r) for r in rows]


def get_trends_for_date(db_path: Path, run_date: date) -> list[PersistedTrend]:
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT * FROM trends WHERE run_date=? ORDER BY id", (run_date.isoformat(),)
        ).fetchall()
    return [_row_to_trend(r) for r in rows]


def get_trend_by_slug(db_path: Path, run_date: date, slug: str) -> PersistedTrend | None:
    with _conn(db_path) as con:
        row = con.execute(
            "SELECT * FROM trends WHERE run_date=? AND slug=?",
            (run_date.isoformat(), slug),
        ).fetchone()
    return _row_to_trend(row) if row else None


def get_available_dates(db_path: Path) -> list[date]:
    """Return all dates with completed daily runs, most recent first."""
    with _conn(db_path) as con:
        rows = con.execute(
            """SELECT DISTINCT run_date FROM runs
               WHERE kind='daily' AND state IN ('completed','completed_with_warnings')
               ORDER BY run_date DESC"""
        ).fetchall()
    return [date.fromisoformat(row["run_date"]) for row in rows]


def fingerprint_exists_in_window(db_path: Path, fingerprint: str, window_days: int) -> bool:
    with _conn(db_path) as con:
        row = con.execute(
            "SELECT 1 FROM trends WHERE fingerprint=? AND run_date >= date('now', ?)",
            (fingerprint, f"-{window_days} days"),
        ).fetchone()
    return row is not None


def _row_to_trend(row: sqlite3.Row) -> PersistedTrend:
    sources_raw = json.loads(row["sources_json"])
    sources = [Source(**s) for s in sources_raw]
    return PersistedTrend(
        id=row["id"],
        run_id=row["run_id"],
        run_date=date.fromisoformat(row["run_date"]),
        slug=row["slug"],
        headline=row["headline"],
        one_liner=row["one_liner"],
        detailed_markdown=row["detailed_markdown"],
        key_points=json.loads(row["key_points_json"]),
        sources=sources,
        fingerprint=row["fingerprint"],
        seen_again=row["seen_again"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


# ── Chat messages ──────────────────────────────────────────────────────────────

def append_chat_message(
    db_path: Path,
    run_id: str,
    run_date: date,
    slug: str,
    role: str,
    content: str,
    citations: list | None = None,
    used_web: bool = False,
) -> int:
    with _conn(db_path) as con:
        cur = con.execute(
            """INSERT INTO chat_messages
               (run_id, run_date, slug, role, content, citations_json, used_web, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                run_id,
                run_date.isoformat(),
                slug,
                role,
                content,
                json.dumps(citations or []),
                1 if used_web else 0,
                datetime.utcnow().isoformat(),
            ),
        )
        con.commit()
        return cur.lastrowid


def list_chat_messages(
    db_path: Path,
    run_date: date | None = None,
    run_id: str | None = None,
    slug: str | None = None,
    limit: int = 100,
) -> list[dict]:
    with _conn(db_path) as con:
        if run_id:
            rows = con.execute(
                "SELECT * FROM chat_messages WHERE run_id=? AND slug=? ORDER BY created_at LIMIT ?",
                (run_id, slug, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM chat_messages WHERE run_date=? AND slug=? ORDER BY created_at LIMIT ?",
                (run_date.isoformat() if run_date else "", slug, limit),
            ).fetchall()
    return [
        {
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "citations": json.loads(r["citations_json"]),
            "used_web": bool(r["used_web"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ── Insights ───────────────────────────────────────────────────────────────────

def create_insight(
    db_path: Path,
    run_id: str,
    run_date: date,
    slug: str,
    user_perspective: str,
    summary: str = "",
    tags: list[str] | None = None,
) -> int:
    now = datetime.utcnow().isoformat()
    with _conn(db_path) as con:
        cur = con.execute(
            """INSERT INTO insights
               (run_id, run_date, slug, user_perspective, summary, tags_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (run_id, run_date.isoformat(), slug, user_perspective, summary, json.dumps(tags or []), now, now),
        )
        con.commit()
        return cur.lastrowid


def list_insights(
    db_path: Path,
    run_date: date | None = None,
    run_id: str | None = None,
    slug: str | None = None,
) -> list[dict]:
    with _conn(db_path) as con:
        if run_id:
            rows = con.execute(
                "SELECT * FROM insights WHERE run_id=? AND slug=? ORDER BY created_at",
                (run_id, slug),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM insights WHERE run_date=? AND slug=? ORDER BY created_at",
                (run_date.isoformat() if run_date else "", slug),
            ).fetchall()
    return [
        {
            "id": r["id"],
            "user_perspective": r["user_perspective"],
            "summary": r["summary"],
            "tags": json.loads(r["tags_json"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]
