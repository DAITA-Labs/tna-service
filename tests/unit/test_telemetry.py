"""Tests for app/core/telemetry — collector registration + label use."""
from prometheus_client import REGISTRY
from app.core.telemetry import (
    extraction_duration_seconds, extraction_pli_count,
    agent_duration_seconds, agent_retry_count,
    agent_tokens_input, agent_tokens_output,
    validator_findings_total, llm_inference_duration_seconds,
)


def test_all_collectors_registered():
    names = {m.name for m in REGISTRY.collect()}
    assert "extraction_duration_seconds" in names
    assert "extraction_pli_count" in names
    assert "agent_duration_seconds" in names
    assert "agent_retry_count" in names
    assert "agent_tokens_input" in names
    assert "agent_tokens_output" in names
    assert "validator_findings" in names
    assert "llm_inference_duration_seconds" in names


def test_agent_duration_labels_per_agent():
    agent_duration_seconds.labels(agent="boundary_finder").observe(0.5)
    samples = [s for m in REGISTRY.collect() if m.name == "agent_duration_seconds"
               for s in m.samples]
    assert any(s.labels.get("agent") == "boundary_finder" for s in samples)


def test_validator_findings_per_check():
    validator_findings_total.labels(check="coverage", severity="warn").inc()
    samples = [s for m in REGISTRY.collect() if m.name == "validator_findings"
               for s in m.samples]
    assert any(
        s.labels.get("check") == "coverage" and s.labels.get("severity") == "warn"
        for s in samples
    )
