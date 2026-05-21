"""LayoutHinter Haystack component — self-aware wrapper around LayoutHinterAgent.

Self-aware: returns the input plan unchanged when there are no Tier-1 ERROR
findings; only invokes the LLM agent when an error is present.  Applies
identity_column_suggestion to the plan when the agent returns one.
"""
from __future__ import annotations

from typing import Any

from haystack import component

from app.agents._base import AgentRunFailure
from app.agents.layout_hinter import LayoutHinterAgent
from app.agents.layout_hinter.schema import LayoutHinterInputs
from app.components._base import Component
from app.components.planner.surveyor import survey_sheet
from app.enums.validation_severity import ValidationSeverity
from app.inferencing._base import BaseProvider
from app.models.artifacts import SheetPlan, ValidationFinding


@component
class LayoutHinter(Component):
    """Self-aware: returns the input plan unchanged if no Tier-1 errors; else
    invokes the LLM and applies the identity_column_suggestion if present.
    """

    def __init__(self, llm: BaseProvider) -> None:
        """Construct the wrapped agent + remember the LLM provider."""
        Component.__init__(self)
        self._agent = LayoutHinterAgent()
        self._llm = llm

    @component.output_types(plan=SheetPlan)
    def run(
        self,
        workbook_ctx: Any,
        plan: SheetPlan,
        findings: list[ValidationFinding],
        sheet: str,
    ) -> dict:
        """Pass plan through unchanged if no errors; otherwise invoke the LLM agent."""
        errors = [f for f in findings if f.severity is ValidationSeverity.ERROR]
        if not errors:
            return {"plan": plan}
        signals = survey_sheet(workbook_ctx, sheet)
        result = self._agent.run(
            ctx=workbook_ctx,
            inputs=LayoutHinterInputs(sheet=sheet, signals=signals),
            provider=self._llm,
        )
        if isinstance(result, AgentRunFailure):
            self.log.warning("agent_fallback_used", agent="layout_hinter")
            return {"plan": plan}
        if result.identity_column_suggestion:
            return {"plan": plan.model_copy(
                update={"identity_column": result.identity_column_suggestion}
            )}
        return {"plan": plan}
