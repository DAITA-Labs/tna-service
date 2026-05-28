"""IdentifierPhaseJudge tuning knobs."""
from __future__ import annotations

from pydantic import Field

from app.inferencing.tuning import AgentTuning


class IdentifierPhaseJudgeTuning(AgentTuning):
    """Per-agent tuning for IdentifierPhaseJudge."""

    semantic_examples:     list[dict] = Field(default_factory=list)
    anti_pattern_examples: list[dict] = Field(default_factory=list)
