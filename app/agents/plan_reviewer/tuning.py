"""PlanReviewer tuning knobs."""
from __future__ import annotations

from pydantic import Field

from app.inferencing.tuning import AgentTuning


class PlanReviewerTuning(AgentTuning):
    """Per-agent tuning for PlanReviewer."""

    confidence_gate: float = 0.85  # plan confidence threshold for firing reviewer
    max_corrections: int = 5  # prompt rule: row_corrections ≤ 5
    semantic_examples: list[dict] = Field(default_factory=list)
    anti_pattern_examples: list[dict] = Field(default_factory=list)
