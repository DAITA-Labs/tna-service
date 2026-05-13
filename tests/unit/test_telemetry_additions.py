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
