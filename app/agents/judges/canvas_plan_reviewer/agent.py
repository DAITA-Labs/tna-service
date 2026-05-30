"""CanvasPlanReviewer agent — single LLM call over the assembled CanvasPlan."""
from __future__ import annotations

from typing import Any

from app.agents._base import Agent, InputVerdict, OutputVerdict
from app.agents.judges.canvas_plan_reviewer.schema import (
    CanvasPlanReviewerInputs,
    PlanReviewVerdict,
)
from app.agents.judges.canvas_plan_reviewer.tuning import (
    CanvasPlanReviewerTuning,
)
from app.agents.judges.canvas_plan_reviewer.validators import (
    validate_plan_review_verdict,
)
from app.prompts.judges import CANVAS_PLAN_REVIEWER


class CanvasPlanReviewerAgent(Agent):
    """LLM as reviewer: judge an assembled CanvasPlan → approve / repick / escalate."""

    name          = "canvas_plan_reviewer"
    prompt        = CANVAS_PLAN_REVIEWER
    output_schema = PlanReviewVerdict
    tuning        = CanvasPlanReviewerTuning()

    def build_input(self, ctx: Any, inputs: CanvasPlanReviewerInputs) -> str:
        """Render the per-call body from pre-formatted summaries + warnings."""
        lines: list[str] = [
            "## Plan summary",
            inputs.plan_summary.strip() or "(empty plan)",
            "",
            "## Scoreboard summary",
            inputs.scoreboard_summary.strip() or "(no scoreboards)",
            "",
        ]
        if inputs.warnings:
            lines.append("## Validator warnings")
            for w in inputs.warnings:
                lines.append(f"  [{w.severity}] {w.name}: {w.message}")
            lines.append("")
        if inputs.cluster_context:
            lines.append("## Cluster context")
            lines.append(f"  {inputs.cluster_context}")
        return "\n".join(lines)

    def validate_input(self, user_text: str) -> InputVerdict:
        return InputVerdict.ok()

    def validate_output(self, output: PlanReviewVerdict, ctx: Any) -> OutputVerdict:
        return validate_plan_review_verdict(output, ctx)
