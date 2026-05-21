"""LayoutHinter tuning knobs."""
from __future__ import annotations

from pydantic import Field

from app.inferencing.tuning import AgentTuning


class LayoutHinterTuning(AgentTuning):
    """Per-agent tuning for LayoutHinter."""

    confidence_gate: float = 0.0
    semantic_examples: list[dict] = Field(default_factory=list)
    anti_pattern_examples: list[dict] = Field(default_factory=list)
