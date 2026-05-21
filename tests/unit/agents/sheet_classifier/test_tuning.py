"""SheetClassifierTuning defaults and per-agent fields."""
from __future__ import annotations

from app.agents.sheet_classifier.tuning import SheetClassifierTuning
from app.inferencing.tuning import AgentTuning


def test_tuning_inherits_agent_tuning() -> None:
    assert issubclass(SheetClassifierTuning, AgentTuning)


def test_tuning_base_defaults() -> None:
    t = SheetClassifierTuning()
    assert t.max_retries == 1
    assert t.capture_decision_notes is False
    assert t.sample_rows == 8


def test_tuning_per_agent_defaults() -> None:
    t = SheetClassifierTuning()
    assert t.confidence_gate == 0.0
    assert t.semantic_examples == []
    assert t.anti_pattern_examples == []


def test_tuning_per_agent_fields_settable() -> None:
    t = SheetClassifierTuning(confidence_gate=0.5, semantic_examples=[{"q": 1}])
    assert t.confidence_gate == 0.5
    assert t.semantic_examples == [{"q": 1}]
