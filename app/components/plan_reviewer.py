"""PlanReviewer Haystack component — self-aware wrapper around PlanReviewerAgent.

Self-aware: returns the input plan unchanged unless there are WARN-severity
findings, the plan confidence is below 0.85, or the mode is non-ROW_PER_PLI.
When the agent returns a needs_fix verdict, row_corrections are applied to
plan.rows.
"""
from __future__ import annotations

from typing import Any

from haystack import component

from app.agents._base import AgentRunFailure
from app.agents.plan_reviewer import PlanReviewerAgent
from app.agents.plan_reviewer.schema import PlanReviewerInputs
from app.components._base import Component
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.validation_severity import ValidationSeverity
from app.inferencing._base import BaseProvider
from app.models.artifacts import SheetPlan, ValidationFinding

_CONFIDENCE_GATE = 0.85


@component
class PlanReviewer(Component):
    """Self-aware: returns input plan unchanged unless warns / low_conf / rare mode."""

    def __init__(self, llm: BaseProvider) -> None:
        """Construct the wrapped agent + remember the LLM provider."""
        Component.__init__(self)
        self._agent = PlanReviewerAgent()
        self._llm = llm

    @component.output_types(plan=SheetPlan)
    def run(
        self,
        workbook_ctx: Any,
        plan: SheetPlan,
        findings: list[ValidationFinding] | None = None,
    ) -> dict:
        """Pass plan through unless reviewer conditions are met; apply any corrections."""
        findings = findings or []
        warns = [f for f in findings if f.severity is ValidationSeverity.WARN]
        needs_reviewer = (
            bool(warns)
            or plan.confidence < _CONFIDENCE_GATE
            or plan.pli_mode is not PliMode.ROW_PER_PLI
        )
        if not needs_reviewer:
            return {"plan": plan}
        setattr(workbook_ctx, "plan_rows", [r.idx for r in plan.rows])
        result = self._agent.run(
            ctx=workbook_ctx,
            inputs=PlanReviewerInputs(plan=plan, findings=findings),
            provider=self._llm,
        )
        if isinstance(result, AgentRunFailure):
            self.log.warning("agent_fallback_used", agent="plan_reviewer")
            return {"plan": plan}
        if result.verdict == "needs_fix":
            plan = _apply_row_corrections(plan, result.row_corrections)
        return {"plan": plan}


def _apply_row_corrections(plan: SheetPlan, corrections: list[dict]) -> SheetPlan:
    """Apply row_corrections from a needs_fix verdict to plan.rows."""
    new_rows = list(plan.rows)
    for corr in corrections:
        for i, r in enumerate(new_rows):
            if r.idx == corr.get("row"):
                suggested = corr.get("suggested_role", r.role)
                if isinstance(suggested, str):
                    try:
                        suggested = RowRole(suggested)
                    except ValueError:
                        suggested = r.role
                new_rows[i] = r.model_copy(update={
                    "role": suggested,
                    "anchor_idx": corr.get("anchor_idx", r.anchor_idx),
                })
                break
    return plan.model_copy(update={"rows": new_rows})
