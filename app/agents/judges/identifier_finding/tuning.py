"""IdentifierFindingJudge tuning knobs.

`confidence_threshold` is the gate threshold — findings whose
`confidence` falls below this value get routed to the judge. The
threshold lives on the agent's tuning rather than the gate component
so it can be tuned per-agent without touching pipeline wiring.
"""
from __future__ import annotations

from pydantic import Field

from app.inferencing.tuning import AgentTuning


class IdentifierJudgeTuning(AgentTuning):
    """Per-agent tuning for IdentifierFindingJudge."""

    confidence_threshold:  float = Field(default=0.7, ge=0.0, le=1.0)
    semantic_examples:     list[dict] = Field(default_factory=list)
    anti_pattern_examples: list[dict] = Field(default_factory=list)
