"""AgentTuning model + render_prompt helper for the decision_notes gate."""
from __future__ import annotations

from pydantic import Field

from app.artifacts.agent_io import DECISION_NOTES_DIRECTIVE
from app.pipelines.tuning import Tuning


class AgentTuning(Tuning):
    """Per-agent knobs — extends the pipeline `Tuning` base.

    Concrete agents may subclass this further to add their own thresholds.
    """

    max_retries: int = 1
    capture_decision_notes: bool = False
    sample_rows: int = Field(default=8, ge=1, le=64)


def render_prompt(base: str, *, tuning: AgentTuning) -> str:
    """Append the decision-notes directive to `base` when capture is enabled."""
    if getattr(tuning, "capture_decision_notes", False):
        return base + DECISION_NOTES_DIRECTIVE
    return base
