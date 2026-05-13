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


def _add_otel_context(logger, method_name, event_dict):
    """Inject current span's trace_id / span_id into log context.

    No-op when no span is active (e.g., startup-time logs) or when OTel
    isn't initialised. Safe to leave on always.
    """
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span is None:
            return event_dict
        ctx = span.get_span_context()
        if not ctx or not ctx.is_valid:
            return event_dict
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    except Exception:
        # Tracing is best-effort; never let log emission fail.
        pass
    return event_dict


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Initialise structlog + stdlib logging. Idempotent; call at startup."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors: list = [
        structlog.contextvars.merge_contextvars,
        _add_otel_context,                       # <- injects trace_id/span_id when a span is active
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
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
    return structlog.get_logger(name)
