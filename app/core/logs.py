"""Structured logging via structlog.

Usage anywhere in the service:
    from app.core.logs import get_logger
    log = get_logger(__name__)
    log.info("agent_started", agent="inspector", file="x.xlsx")

JSON output in production, key=value in development. Initialized once via
`configure_logging()` at application startup (called from app/main.py).
"""
import logging
import sys

import structlog

from app.core.tracing import add_trace_context_to_log, emit_to_otel_logs


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Initialise structlog + stdlib logging. Idempotent; call at startup."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors: list = [
        structlog.contextvars.merge_contextvars,
        add_trace_context_to_log,                # <- injects trace_id/span_id when a span is active
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        emit_to_otel_logs,                       # <- side-channel to OTel; pass-through
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "tna_service") -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger for the given name."""
    return structlog.get_logger(name)


