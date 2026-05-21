"""LayoutHinter Haystack component — wraps LayoutHinterAgent."""
from __future__ import annotations

from typing import Any

from haystack import component

from app.agents._base import AgentRunFailure
from app.agents.layout_hinter import LayoutHinterAgent
from app.agents.layout_hinter.schema import LayoutHinterInputs, LayoutHints
from app.components._base import Component
from app.inferencing._base import BaseProvider


@component
class LayoutHinter(Component):
    """Pipeline component that produces LayoutHints from sheet signals."""

    def __init__(self, llm: BaseProvider) -> None:
        """Construct the wrapped agent + remember the LLM provider."""
        Component.__init__(self)
        self._agent = LayoutHinterAgent()
        self._llm = llm

    @component.output_types(hints=LayoutHints)
    def run(self, workbook_ctx: Any, sheet: str, signals: Any) -> dict:
        """Run the agent and fall back to empty LayoutHints() on failure."""
        result = self._agent.run(
            ctx=workbook_ctx,
            inputs=LayoutHinterInputs(sheet=sheet, signals=signals),
            provider=self._llm,
        )
        if isinstance(result, AgentRunFailure):
            self.log.warning("agent_fallback_used", agent="layout_hinter")
            return {"hints": LayoutHints()}
        return {"hints": result}
