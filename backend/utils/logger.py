"""
Centralized logging configuration.

Provides a single get_logger() factory used across the entire codebase
(backend API, agents, RAG pipeline, frontend, etc.) so that every
component logs in a consistent format and to the same rotating files.

Log categories:
    - app.log        general application logs
    - errors.log      ERROR and CRITICAL only
    - requests.log    inbound API / chat requests and responses
    - token_usage.log LLM token usage and latency per call
"""

import json
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from backend.config.settings import get_settings

settings = get_settings()

_LOG_DIR = Path(settings.LOG_DIR)
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_FORMATTER = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_configured_loggers: dict[str, logging.Logger] = {}


def _build_file_handler(filename: str, level: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        filename=_LOG_DIR / filename,
        maxBytes=settings.LOG_FILE_MAX_BYTES,
        backupCount=settings.LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(_FORMATTER)
    handler.setLevel(level)
    return handler


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger for the given module name.

    Every logger writes to:
      - console (stdout)
      - logs/app.log        (all levels >= configured LOG_LEVEL)
      - logs/errors.log     (ERROR and above only)

    Example:
        logger = get_logger(__name__)
        logger.info("Ticket created", extra={"ticket_id": "TCK-0001"})
    """
    if name in _configured_loggers:
        return _configured_loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(_FORMATTER)
        console_handler.setLevel(logger.level)

        logger.addHandler(console_handler)
        logger.addHandler(_build_file_handler("app.log", logger.level))
        logger.addHandler(_build_file_handler("errors.log", logging.ERROR))

    _configured_loggers[name] = logger
    return logger


class RequestLogger:
    """
    Dedicated JSON-lines logger for inbound requests/responses.

    Kept separate from the general app logger so request auditing can be
    parsed independently (e.g. for analytics or compliance review).
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("requests")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        if not self._logger.handlers:
            self._logger.addHandler(_build_file_handler("requests.log", logging.INFO))

    def log(self, **fields: Any) -> None:
        record = {"timestamp": time.time(), **fields}
        self._logger.info(json.dumps(record, default=str))


class TokenUsageLogger:
    """
    Dedicated JSON-lines logger for LLM token usage and latency.

    Every call to the Groq API should report here so cost/usage can be
    reconstructed later even though Groq's free tier has no billing API.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("token_usage")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        if not self._logger.handlers:
            self._logger.addHandler(_build_file_handler("token_usage.log", logging.INFO))

    def log(
        self,
        *,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        latency_ms: float,
        agent: str | None = None,
    ) -> None:
        record = {
            "timestamp": time.time(),
            "model": model,
            "agent": agent,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "latency_ms": round(latency_ms, 2),
        }
        self._logger.info(json.dumps(record))


request_logger = RequestLogger()
token_usage_logger = TokenUsageLogger()
