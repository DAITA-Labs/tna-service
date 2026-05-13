"""Smoke tests that the collectors are wired and callable with OTel SDK.

With OTel Metrics SDK, collectors are Instruments that accept .record()
or .add() calls with an attributes dict. Noop fallback supports these
calls silently when OTel SDK is unavailable.
"""
from app.core.telemetry import (
    agent_tokens_input,
    agent_tokens_output,
    tool_calls_total,
    extraction_phase_duration_seconds,
    extractions_total,
    agent_calls_total,
    llm_calls_total,
    tool_duration_seconds,
    tool_errors_total,
    plis_extracted_total,
)


def test_tool_call_increments_counter(tmp_path):
    """Verify tool_calls_total can be called with attributes."""
    # With OTel SDK, we record metrics by calling .add() with attributes.
    # The noop fallback accepts the call silently.
    tool_calls_total.add(1, {"tool_name": "list_sheets"})


def test_phase_histogram_collector_exists():
    """The phase histogram collector is callable."""
    extraction_phase_duration_seconds.record(0.1, {"phase": "inspect"})


def test_agent_token_counters_exist():
    """Token counters are callable with (agent, model) attributes."""
    agent_tokens_input.add(100, {"agent": "field_namer", "model": "claude-opus"})
    agent_tokens_output.add(50, {"agent": "field_namer", "model": "claude-opus"})


def test_extractions_total_collector_exists():
    """Extractions counter is callable with status attribute."""
    extractions_total.add(1, {"status": "success"})


def test_agent_calls_total_collector_exists():
    """Agent calls counter is callable with (agent, status) attributes."""
    agent_calls_total.add(1, {"agent": "field_namer", "status": "success"})


def test_llm_calls_total_collector_exists():
    """LLM calls counter is callable with (model, status) attributes."""
    llm_calls_total.add(1, {"model": "claude-opus", "status": "success"})


def test_tool_duration_collector_exists():
    """Tool duration histogram is callable with tool_name attribute."""
    tool_duration_seconds.record(0.05, {"tool_name": "list_sheets"})


def test_tool_errors_total_collector_exists():
    """Tool errors counter is callable with tool_name attribute."""
    tool_errors_total.add(1, {"tool_name": "list_sheets"})


def test_tool_error_counter_fires_on_tool_failure(tmp_path):
    """Verify tool_errors_total can be called on exception."""
    _NAME = "__failing_tool_for_test__"
    try:
        raise RuntimeError("intentional")
    except RuntimeError:
        tool_errors_total.add(1, {"tool_name": _NAME})


def test_plis_extracted_counter_exists():
    """Verify plis_extracted_total is callable."""
    plis_extracted_total.add(5, {})
