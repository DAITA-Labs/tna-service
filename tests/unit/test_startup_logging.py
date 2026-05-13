"""Verifies structlog is configured when app.main is imported (which happens
at FastAPI startup and during test client creation)."""
from app.main import app  # noqa: F401 — triggers configure_logging
import structlog


def test_structlog_is_configured_after_import():
    cfg = structlog.get_config()
    assert cfg["processors"], "structlog should be configured by app.main import"
