"""WorkbookSummaryProvider — pipeline component that emits the WorkbookSummary."""
from __future__ import annotations

from typing import Any

from haystack import component

from app.components._base import Component
from app.models.artifacts import WorkbookSummary
from app.tools._registry import TOOL_REGISTRY


@component
class WorkbookSummaryProvider(Component):
    """Pipeline component that emits the WorkbookSummary for a registered workbook."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(summary=WorkbookSummary)
    def run(self, workbook_ctx: Any) -> dict:
        """Call the workbook_summary tool and return the summary."""
        summary: WorkbookSummary = TOOL_REGISTRY.get("workbook_summary")(workbook_ctx)
        return {"summary": summary}
