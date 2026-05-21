"""SheetClassifier Haystack component — wraps SheetClassifierAgent."""
from __future__ import annotations

import types

from haystack import component as hs_component

from app.agents._base import AgentRunFailure
from app.agents.sheet_classifier import SheetClassifierAgent, SheetClassifierInputs
from app.components._base import Component
from app.inferencing._base import BaseProvider


def _ensure_sheet_names_on_ctx(workbook_ctx: object, workbook_summary: object) -> object:
    """Return a context object that exposes sheet_names for validate_output.

    If the ctx already has a sheet_names attribute, return it unchanged.
    Otherwise wrap it with the sheet_names from the summary.
    """
    if getattr(workbook_ctx, "sheet_names", None) is not None:
        return workbook_ctx
    # Build a lightweight proxy that carries sheet_names alongside the original ctx.
    proxy = types.SimpleNamespace(
        **{k: getattr(workbook_ctx, k) for k in dir(workbook_ctx) if not k.startswith("_")}
    ) if workbook_ctx is not None else types.SimpleNamespace()
    proxy.sheet_names = list(getattr(workbook_summary, "sheet_names", []) or [])
    return proxy


@hs_component
class SheetClassifier(Component):
    """Haystack component that filters a workbook down to TNA-relevant sheet names.

    Accepts a WorkbookSummary and produces the list of sheet names that contain
    TNA data; fires once per workbook at the start of the extraction pipeline.
    Falls back to all sheet names on agent failure — false positives are cheap
    and downstream agents can discard irrelevant sheets.
    """

    def __init__(self, llm: BaseProvider) -> None:
        Component.__init__(self)
        self._agent = SheetClassifierAgent()
        self._llm = llm

    @hs_component.output_types(relevant_sheets=list)
    def run(self, workbook_ctx: object, workbook_summary: object) -> dict:
        """Run the sheet-classifier agent and return the relevant sheet names."""
        ctx_with_names = _ensure_sheet_names_on_ctx(workbook_ctx, workbook_summary)
        result = self._agent.run(
            ctx=ctx_with_names,
            inputs=SheetClassifierInputs(workbook_summary=workbook_summary),
            provider=self._llm,
        )
        if isinstance(result, AgentRunFailure):
            self.log.warning("agent_fallback_used", agent="sheet_classifier")
            return {"relevant_sheets": list(getattr(workbook_summary, "sheet_names", []))}
        return {"relevant_sheets": result.relevant_sheets}
