from __future__ import annotations

import asyncio
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from asyncio import Queue

_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9\-_]{8,}", re.IGNORECASE)

# ── Noisy 3rd-party libraries — limit to WARNING ────────────────────────────
_SILENCE = [
    "httpx", "httpcore", "urllib3", "ddgs", "duckduckgo_search",
    "playwright", "crawl4ai", "litellm", "LiteLLM", "openai",
    "asyncio", "multipart",
]

# ── Module-level state for the async log worker ─────────────────────────────
_log_queue: Queue[dict] | None = None
_worker_task: asyncio.Task | None = None


def _redact_secrets(_, __, event_dict: dict) -> dict:
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = _SECRET_PATTERN.sub("[REDACTED]", value)
    return event_dict


class _DBLogHandler(logging.Handler):
    """Logging handler that enqueues structured records for async DB insert."""

    def __init__(self, queue: asyncio.Queue) -> None:
        super().__init__()
        self._queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Pull structlog's event dict if available, otherwise use formatted msg
            event_dict: dict = getattr(record, "structlog_event_dict", {})
            event_key = event_dict.get("event") if event_dict else None
            message = self.format(record) if not event_dict else None

            payload = {
                "ts": datetime.fromtimestamp(record.created, tz=timezone.utc),
                "level": record.levelname,
                "logger_name": record.name[:120],
                "event": str(event_key)[:200] if event_key else None,
                "message": message,
                "data": {k: v for k, v in event_dict.items() if k not in ("event", "level", "logger", "timestamp")}
                        if event_dict else None,
                "run_id": event_dict.get("run_id") if event_dict else None,
            }
            # Non-blocking: drop if queue full (5000 cap prevents memory accumulation)
            try:
                self._queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # drop rather than block the caller
        except Exception:
            self.handleError(record)


async def _flush_worker(queue: asyncio.Queue) -> None:
    """Background task: flush log records to DB in batches."""
    from .db import _get_factory
    from .db_models import LogEvent

    BATCH_SIZE = 200
    FLUSH_INTERVAL = 2.0  # seconds

    while True:
        await asyncio.sleep(FLUSH_INTERVAL)
        batch: list[dict] = []
        try:
            while len(batch) < BATCH_SIZE:
                batch.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            pass

        if not batch:
            continue

        try:
            async with _get_factory()() as session:
                session.add_all([LogEvent(**row) for row in batch])
                await session.commit()
        except Exception as exc:
            # Can't log here (would recurse), so write to stderr
            print(f"[log_flush_error] {exc}", file=sys.stderr)


async def start_log_worker() -> None:
    """Start the background DB log flush worker. Call from app lifespan."""
    global _log_queue, _worker_task
    _log_queue = asyncio.Queue(maxsize=5000)

    # Wire the DB handler now that we have an event loop and queue
    handler = _DBLogHandler(_log_queue)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("backend").addHandler(handler)

    _worker_task = asyncio.create_task(_flush_worker(_log_queue))
    _worker_task.add_done_callback(
        lambda t: t.exception() and print(f"[log_worker_died] {t.exception()}", file=sys.stderr)
    )


async def stop_log_worker() -> None:
    """Drain remaining log records and stop the worker. Call from app lifespan shutdown."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    _worker_task = None

    # Final drain of anything left in the queue
    if _log_queue and not _log_queue.empty():
        from .db import _get_factory
        from .db_models import LogEvent

        batch: list[dict] = []
        while not _log_queue.empty():
            try:
                batch.append(_log_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if batch:
            try:
                async with _get_factory()() as session:
                    session.add_all([LogEvent(**row) for row in batch])
                    await session.commit()
            except Exception as exc:
                print(f"[log_shutdown_flush_error] {exc}", file=sys.stderr)


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> None:
    # Silence noisy 3rd-party loggers
    for name in _SILENCE:
        logging.getLogger(name).setLevel(logging.WARNING)

    # Root logger at WARNING — prevent 3rd-party noise reaching our handlers
    logging.getLogger().setLevel(logging.WARNING)

    # Our application logger at the requested level, no propagation to root
    app_logger = logging.getLogger("backend")
    app_logger.setLevel(level)
    app_logger.propagate = False

    # Stream handler for local dev (stderr) — DB handler wired later in start_log_worker()
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    app_logger.addHandler(stream_handler)

    structlog.configure(
        processors=[
            _redact_secrets,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _inject_event_dict,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _inject_event_dict(logger, method, event_dict: dict) -> dict:
    """Stash the structlog event dict on the stdlib LogRecord so _DBLogHandler can read it."""
    # This runs as a structlog processor; the next processor renders to JSON string.
    # We store the raw dict in a thread-local that the handler can pick up.
    _current_event_dict.event_dict = dict(event_dict)
    return event_dict


class _EventDictStash:
    event_dict: dict = {}


_current_event_dict = _EventDictStash()


# Patch _DBLogHandler.emit to pick up the stashed event dict
_orig_emit = _DBLogHandler.emit


def _patched_emit(self, record: logging.LogRecord) -> None:
    if not hasattr(record, "structlog_event_dict"):
        record.structlog_event_dict = dict(_current_event_dict.event_dict)  # type: ignore[attr-defined]
        _current_event_dict.event_dict = {}
    _orig_emit(self, record)


_DBLogHandler.emit = _patched_emit  # type: ignore[method-assign]


def get_logger(name: str = "trend_agent") -> structlog.stdlib.BoundLogger:
    # Ensure all app loggers are under the "backend" namespace so our handler picks them up
    if not name.startswith("backend"):
        name = f"backend.{name}"
    return structlog.get_logger(name)
