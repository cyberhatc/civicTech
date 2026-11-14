"""Logging setup with automatic PII redaction on every record."""

from __future__ import annotations

import logging
import sys

from app.core.guardrails import sanitize_for_log

_PII_LOGGERS = (
    "app.services.llm",
    "app.services.stt",
    "app.services.tts",
    "app.routers.voice",
    "app.routers.chat",
)


class RedactingFormatter(logging.Formatter):
    """Formatter that masks Aadhaar / phone numbers before a record is emitted."""

    def format(self, record: logging.LogRecord) -> str:
        original = record.getMessage()
        redacted = sanitize_for_log(original)
        record.msg = redacted
        record.args = ()
        return super().format(record)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        RedactingFormatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)-28s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    for name in _PII_LOGGERS:
        logging.getLogger(name).setLevel(level.upper())

    # Third-party noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
