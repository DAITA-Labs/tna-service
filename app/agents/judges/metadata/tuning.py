"""MetadataFindingJudge tuning knobs."""
from __future__ import annotations

from pydantic import Field

from app.inferencing.tuning import AgentTuning


class MetadataJudgeTuning(AgentTuning):
    """Per-agent tuning for MetadataFindingJudge."""

    semantic_examples:     list[dict] = Field(default_factory=list)
    anti_pattern_examples: list[dict] = Field(default_factory=list)
