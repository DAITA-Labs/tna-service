"""Cross-cutting framework concerns — logging, telemetry, middleware."""
from app.core.logs import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger"]
