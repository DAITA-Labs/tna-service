"""LayoutHinterTuning defaults and per-agent fields."""
from __future__ import annotations

from app.agents.layout_hinter.tuning import LayoutHinterTuning
from app.inferencing.tuning import AgentTuning


def test_tuning_inherits_agent_tuning() -> None:
    assert issubclass(LayoutHinterTuning, AgentTuning)


def test_tuning_base_defaults() -> None:
    t = LayoutHinterTuning()
    assert t.max_retries == 1
    assert t.capture_decision_notes is False
    assert t.sample_rows == 8


def test_tuning_per_agent_defaults() -> None:
    t = LayoutHinterTuning()
    assert t.confidence_gate == 0.0
    assert t.semantic_examples == []
    assert t.anti_pattern_examples == []


def test_tuning_per_agent_fields_settable() -> None:
    t = LayoutHinterTuning(confidence_gate=0.7, semantic_examples=[{"col": "B"}])
    assert t.confidence_gate == 0.7
    assert t.semantic_examples == [{"col": "B"}]
