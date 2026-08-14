"""structlog (slog-style) setup."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from .log_feedback import log_feedback_processor

SERVICE_NAME = "h3c-tv-agent"


def _add_service_and_msg(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    event_dict.setdefault("service", SERVICE_NAME)
    if "event" in event_dict and "msg" not in event_dict:
        event_dict["msg"] = event_dict["event"]
    return event_dict


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    # Paramiko 默认 INFO 会打明文 "Authentication (password) successful!"，
    # 无 JSON level → Loki detected_level=unknown；降到 WARNING。
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="ts"),
        _add_service_and_msg,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        log_feedback_processor,
    ]
    if fmt.strip().lower() == "console":
        renderer: object = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "h3c_tv_agent"):
    return structlog.get_logger(name)
