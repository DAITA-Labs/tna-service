"""PlanReviewerTuning defaults and per-agent fields."""
from __future__ import annotations

from app.agents.plan_reviewer.tuning import PlanReviewerTuning
from app.inferencing.tuning import AgentTuning


def test_tuning_inherits_agent_tuning() -> None:
    assert issubclass(PlanReviewerTuning, AgentTuning)


def test_tuning_base_defaults() -> None:
    t = PlanReviewerTuning()
    assert t.max_retries == 1
    assert t.capture_decision_notes is False


def test_tuning_per_agent_defaults() -> None:
    t = PlanReviewerTuning()
    assert t.confidence_gate == 0.85
    assert t.max_corrections == 5
    assert t.semantic_examples == []
    assert t.anti_pattern_examples == []


def test_tuning_per_agent_fields_settable() -> None:
    t = PlanReviewerTuning(
        confidence_gate=0.7,
        max_corrections=3,
        semantic_examples=[{"row": 1, "role": "anchor"}],
    )
    assert t.confidence_gate == 0.7
    assert t.max_corrections == 3
    assert t.semantic_examples == [{"row": 1, "role": "anchor"}]
