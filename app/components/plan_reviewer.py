"""PlanReviewer Haystack component — wraps PlanReviewerAgent.

The wrapper attaches `plan_rows: list[int]` to the workbook ctx so the
agent's load-bearing validate_output can verify that every row referenced
in the LLM's row_corrections actually exists in plan.rows. On agent failure,
falls back to a low-confidence `looks_correct` verdict — same surface as
the legacy implementation.
"""
from __future__ import annotations

from typing import Any

from haystack import component

from app.agents._base import AgentRunFailure
from app.agents.plan_reviewer import PlanReviewerAgent
from app.agents.plan_reviewer.schema import PlanReviewerInputs, PlanVerdict
from app.components._base import Component
from app.inferencing._base import BaseProvider
from app.models.artifacts import SheetPlan, ValidationFinding


@component
class PlanReviewer(Component):
    """Pipeline component that reviews a SheetPlan for correctness."""

    def __init__(self, llm: BaseProvider) -> None:
        """Construct the wrapped agent + remember the LLM provider."""
        Component.__init__(self)
        self._agent = PlanReviewerAgent()
        self._llm = llm

    @component.output_types(verdict=PlanVerdict)
    def run(
        self, workbook_ctx: Any, plan: SheetPlan,
        findings: list[ValidationFinding] | None = None,
    ) -> dict:
        """Run the agent; fall back to low-confidence looks_correct on failure."""
        ctx_with_rows = _attach_plan_rows(workbook_ctx, plan)
        result = self._agent.run(
            ctx=ctx_with_rows,
            inputs=PlanReviewerInputs(plan=plan, findings=findings or []),
            provider=self._llm,
        )
        if isinstance(result, AgentRunFailure):
            self.log.warning("agent_fallback_used", agent="plan_reviewer")
            return {"verdict": PlanVerdict(verdict="looks_correct", confidence=0.0)}
        return {"verdict": result}


def _attach_plan_rows(workbook_ctx: Any, plan: SheetPlan) -> Any:
    """Set ctx.plan_rows to the list of row indices in plan.rows."""
    setattr(workbook_ctx, "plan_rows", [r.idx for r in plan.rows])
    return workbook_ctx
