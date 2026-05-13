"""Smoke tests that the new collectors are wired and increment correctly."""
from app.core.telemetry import (
    agent_tokens_input,
    agent_tokens_output,
    tool_calls_total,
    extraction_phase_duration_seconds,
)
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
import app.repositories.workbook_tools.survey  # noqa: F401 — register
from app.repositories.workbook_repo import register_workbook, clear_cache
from openpyxl import Workbook


def test_tool_call_increments_counter(tmp_path):
    clear_cache()
    wb = Workbook()
    wb.active["A1"] = "x"
    p = tmp_path / "x.xlsx"
    wb.save(p)
    ctx = register_workbook(p)
    before = tool_calls_total.labels(tool_name="list_sheets")._value.get()
    TOOL_REGISTRY.get("list_sheets")(ctx)
    after = tool_calls_total.labels(tool_name="list_sheets")._value.get()
    assert after == before + 1


def test_phase_histogram_collector_exists():
    """The collector is defined and has 'phase' as a label."""
    assert "phase" in extraction_phase_duration_seconds._labelnames


def test_agent_token_counters_exist():
    """Token counters are defined with (agent, model) labels."""
    assert agent_tokens_input._labelnames == ("agent", "model")
    assert agent_tokens_output._labelnames == ("agent", "model")


from app.core.telemetry import (
    extractions_total, agent_calls_total, llm_calls_total,
    tool_duration_seconds, tool_errors_total,
)


def test_extractions_total_collector_exists():
    assert "status" in extractions_total._labelnames


def test_agent_calls_total_collector_exists():
    assert agent_calls_total._labelnames == ("agent", "status")


def test_llm_calls_total_collector_exists():
    assert llm_calls_total._labelnames == ("model", "status")


def test_tool_duration_collector_exists():
    assert "tool_name" in tool_duration_seconds._labelnames


def test_tool_errors_total_collector_exists():
    assert "tool_name" in tool_errors_total._labelnames


def test_tool_error_counter_fires_on_tool_failure(tmp_path):
    """When a registered tool raises, tool_errors_total{tool_name} increments."""
    from app.repositories.workbook_tools._registry import TOOL_REGISTRY, tool

    _NAME = "__failing_tool_for_test__"
    if _NAME not in TOOL_REGISTRY._tools:
        @tool(_NAME)
        def _failing_tool():
            raise RuntimeError("intentional")

    before = tool_errors_total.labels(tool_name=_NAME)._value.get()
    try:
        TOOL_REGISTRY.get(_NAME)()
    except RuntimeError:
        pass
    after = tool_errors_total.labels(tool_name=_NAME)._value.get()
    assert after == before + 1


def test_plis_extracted_counter_exists():
    from app.core.telemetry import plis_extracted_total
    # It's an unlabeled Counter; verify it has _value attribute and starts at zero or ≥0
    assert plis_extracted_total._value.get() >= 0
