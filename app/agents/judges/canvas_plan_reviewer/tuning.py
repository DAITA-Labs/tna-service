"""CanvasPlanReviewer tuning knobs.

`min_winner_score` is the gate's per-canonical floor: when any winning
field location scored below it, the plan is routed to the reviewer
even in the absence of warnings. Tuning lives on the agent so the
gate doesn't need to learn it independently.
"""
from __future__ import annotations

from pydantic import Field

from app.inferencing.tuning import AgentTuning


class CanvasPlanReviewerTuning(AgentTuning):
    """Per-agent tuning for CanvasPlanReviewer."""

    # Any field_location whose score is below this triggers review.
    min_winner_score: float = Field(default=0.6, ge=0.0, le=1.0)
