"""PlanReviewer Agent — LLM judge of SheetPlan correctness."""
from __future__ import annotations

from typing import Any

from app.agents._base import Agent, InputVerdict, OutputVerdict
from app.agents.plan_reviewer.schema import PlanReviewerInputs, PlanVerdict
from app.agents.plan_reviewer.tuning import PlanReviewerTuning
from app.agents.plan_reviewer.validators import validate_plan_verdict
from app.prompts import PLAN_REVIEWER
from app.tools._registry import TOOL_REGISTRY


class PlanReviewerAgent(Agent):
    """Single-call LLM agent: SheetPlan + findings + cell peek → PlanVerdict."""

    name = "plan_reviewer"
    prompt = PLAN_REVIEWER
    output_schema = PlanVerdict
    tuning = PlanReviewerTuning()

    def build_input(self, ctx: Any, inputs: PlanReviewerInputs) -> str:
        """Assemble the prompt body from a SheetPlan + findings + a 20x15 cell peek."""
        plan = inputs.plan
        peek = TOOL_REGISTRY.get("peek_sheet")
        grid = peek(ctx, plan.sheet, rows=20, cols=15)
        lines = [
            f"# Sheet: {plan.sheet}",
            "## Plan summary:",
            str(plan.model_dump(mode="json", exclude_none=True)),
            "",
            "## Tier 1/2 warnings:",
        ]
        for f in inputs.findings:
            lines.append(f"  - [{f.severity}] {f.check}: {f.message}")
        lines.append("")
        lines.append("## Sheet peek (rows 1..20, cols 1..15):")
        for c in grid.cells:
            lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
        return "\n".join(lines)

    def validate_input(self, user_text: str) -> InputVerdict:
        """No-op input validation — Pydantic guards the structural shape."""
        return InputVerdict.ok()

    def validate_output(self, output: PlanVerdict, ctx: Any) -> OutputVerdict:
        """Delegate to the load-bearing plan-verdict validator."""
        return validate_plan_verdict(output, ctx)
