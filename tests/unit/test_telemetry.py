"""Tests for app/core/telemetry — OTel Metrics SDK collectors.

With OTel instrumentation, telemetry collectors are instances of OTel Instruments
(Counter, Histogram, etc.) or noop stubs when the SDK is unavailable. These tests
verify that all expected collectors exist and can be called without errors.
"""
from app.core.telemetry import (
    extraction_duration_seconds, extraction_pli_count,
    agent_duration_seconds, agent_retry_count,
    agent_tokens_input, agent_tokens_output,
    validator_findings_total, llm_inference_duration_seconds,
    extractions_total, agent_calls_total, llm_calls_total, tool_calls_total,
)


def test_all_collectors_exist():
    """Verify all expected collectors are defined and callable."""
    # Extraction collectors
    assert extraction_duration_seconds is not None
    assert extraction_pli_count is not None
    assert extractions_total is not None

    # Agent collectors
    assert agent_duration_seconds is not None
    assert agent_retry_count is not None
    assert agent_tokens_input is not None
    assert agent_tokens_output is not None
    assert agent_calls_total is not None

    # LLM collectors
    assert llm_inference_duration_seconds is not None
    assert llm_calls_total is not None

    # Validator collectors
    assert validator_findings_total is not None

    # Tool collectors
    assert tool_calls_total is not None


def test_agent_duration_record():
    """Verify agent_duration_seconds.record() accepts attributes."""
    # record() should accept a value and attributes dict without error
    agent_duration_seconds.record(0.5, {"agent": "field_namer", "status": "success"})


def test_validator_findings_add():
    """Verify validator_findings_total.add() accepts attributes."""
    # add() should accept a value and attributes dict without error
    validator_findings_total.add(1, {"check": "coverage", "severity": "warn"})
