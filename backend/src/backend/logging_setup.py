from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from pathlib import Path

import structlog

_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9\-_]{8,}", re.IGNORECASE)


def _redact_secrets(_, __, event_dict: dict) -> dict:
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = _SECRET_PATTERN.sub("[REDACTED]", value)
    return event_dict


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "agent.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    stream_handler = logging.StreamHandler(sys.stdout)

    logging.basicConfig(
        format="%(message)s",
        handlers=[file_handler, stream_handler],
        level=level,
    )

    structlog.configure(
        processors=[
            _redact_secrets,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "trend_agent") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
