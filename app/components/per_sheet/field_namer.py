"""FieldNamer Haystack component — wraps FieldNamerAgent."""
from __future__ import annotations

from typing import Any

from haystack import component

from app.agents._base import AgentRunFailure
from app.agents.field_namer import FieldNamerAgent
from app.agents.field_namer.schema import CanonicalNameMap, FieldNamerInputs
from app.components._base import Component
from app.inferencing._base import BaseProvider
from app.models.artifacts import SheetPlan


@component
class FieldNamer(Component):
    """Pipeline component that produces CanonicalNameMap from a SheetPlan."""

    def __init__(self, llm: BaseProvider) -> None:
        """Construct the wrapped agent + remember the LLM provider."""
        Component.__init__(self)
        self._agent = FieldNamerAgent()
        self._llm = llm

    @component.output_types(name_map=CanonicalNameMap)
    def run(self, workbook_ctx: Any, plan: SheetPlan) -> dict:
        """Run the agent and fall back to empty CanonicalNameMap on failure."""
        result = self._agent.run(
            ctx=workbook_ctx,
            inputs=FieldNamerInputs(plan=plan),
            provider=self._llm,
        )
        if isinstance(result, AgentRunFailure):
            self.log.warning("agent_fallback_used", agent="field_namer")
            return {"name_map": CanonicalNameMap()}
        return {"name_map": result}
