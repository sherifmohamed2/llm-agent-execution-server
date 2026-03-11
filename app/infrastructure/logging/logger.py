from __future__ import annotations
import logging
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import structlog

from app.core.config import settings

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)


def add_context(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    req_id = request_id_ctx.get()
    t_id = trace_id_ctx.get()
    if req_id:
        event_dict["request_id"] = req_id
    if t_id:
        event_dict["trace_id"] = t_id
    return event_dict


def configure_logging() -> None:
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            add_context,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root = logging.getLogger()
    root.setLevel(log_level)

    # Always log to stdout so you see logs in the terminal.
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(log_level)
        root.addHandler(stream_handler)

    # Additionally, log to a file if a path is configured.
    log_file = settings.log_file_path
    if log_file:
        log_path = Path(log_file)
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setLevel(log_level)
            root.addHandler(file_handler)
        except Exception:
            # If file logging fails for some reason, we still want stdout logging to work.
            # We deliberately swallow the exception here to avoid breaking app startup.
            root.error("log_file_setup_failed", log_file=str(log_file))


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
