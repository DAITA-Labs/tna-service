"""Shared fixtures for the test suite."""
from pathlib import Path
import pytest
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# Re-export the fixture loader so any tier can use @fixture_case.
from tests.fixtures.conftest import fixture  # noqa: F401


# Dataset ships inside tna-service/ so the microservice is self-contained.
# tests/conftest.py → tests → tna-service → dataset
DATASET_DIR = Path(__file__).resolve().parents[1] / "dataset"

# ---------------------------------------------------------------------------
# Shared OTel in-memory exporter — set up ONCE for the whole test session so
# multiple test modules don't fight over set_tracer_provider (which is a
# one-shot global).  Individual tests clear it via the autouse fixture below.
# ---------------------------------------------------------------------------
SPAN_EXPORTER = InMemorySpanExporter()
_test_tracer_provider = TracerProvider()
_test_tracer_provider.add_span_processor(SimpleSpanProcessor(SPAN_EXPORTER))
trace.set_tracer_provider(_test_tracer_provider)


@pytest.fixture(autouse=True)
def _reset_otel_spans():
    """Clear the shared in-memory span exporter before every test."""
    SPAN_EXPORTER.clear()
    yield
    SPAN_EXPORTER.clear()


@pytest.fixture(autouse=True)
def _reset_structlog():
    """Reset structlog to a test-friendly state before every test.

    Three hazards introduced by Haystack's __init__ (which calls
    structlog.configure at import time) are neutralised here:

    1. cache_logger_on_first_use=True — freezes the processor chain on first
       use, making subsequent capture_logs() blocks invisible.

    2. logger_factory=stdlib.LoggerFactory — routes output through the stdlib
       logging module; capture_logs() swaps processors but stdlib-backed loggers
       bypass the structlog processor chain entirely.

    3. wrapper_class=BoundLoggerFilteringAtWarning — silently drops .info()
       calls, so agent.input / agent.output log events never fire.

    Resetting all three to test-friendly defaults ensures capture_logs() works
    correctly in any test that exercises Haystack-based agents.
    """
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(0),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    yield


@pytest.fixture
def dkn_file():
    p = DATASET_DIR / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx"
    assert p.exists(), f"expected dataset file at {p}"
    return p


@pytest.fixture
def compass_pro_manos_file():
    p = DATASET_DIR / "20260304 MOPD W26(1) MANOS COMPASS PRO.xlsx"
    assert p.exists(), f"expected dataset file at {p}"
    return p


@pytest.fixture
def northern_reflections_file():
    p = DATASET_DIR / "NORTHERN REFLECTIONS- T&a.xlsx"
    assert p.exists(), f"expected dataset file at {p}"
    return p


@pytest.fixture
def orders_plan_file():
    p = DATASET_DIR / "63261-TNA.xlsx"
    assert p.exists(), f"expected dataset file at {p}"
    return p


@pytest.fixture
def christian_berg_file():
    p = DATASET_DIR / "CHRISTIAN BERG- T&A.xlsx"
    assert p.exists(), f"expected dataset file at {p}"
    return p


@pytest.fixture(autouse=True)
def _clear_workbook_cache():
    from app.repositories.workbook_repo import clear_cache
    clear_cache()
    yield
    clear_cache()
