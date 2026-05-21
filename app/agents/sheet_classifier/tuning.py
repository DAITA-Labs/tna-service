"""SheetClassifier per-agent tuning knobs."""
from __future__ import annotations

from pydantic import Field

from app.inferencing.tuning import AgentTuning


class SheetClassifierTuning(AgentTuning):
    """Tuning knobs specific to SheetClassifierAgent."""

    confidence_gate: float = 0.0
    semantic_examples: list[dict] = Field(default_factory=list)
    anti_pattern_examples: list[dict] = Field(default_factory=list)
