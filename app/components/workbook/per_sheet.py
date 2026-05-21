"""PerSheetProcessor — runs the per-sheet sub-pipeline once per sheet."""
from __future__ import annotations

from typing import Any

from haystack import component

from app.components._base import Component
from app.inferencing._base import BaseProvider


@component
class PerSheetProcessor(Component):
    """Runs the per-sheet sub-pipeline once per sheet; aggregates PLIs, warnings, format."""

    def __init__(self, llm: BaseProvider) -> None:
        Component.__init__(self)
        self._llm = llm
        # Import here to avoid circular import; make_per_sheet_pipeline is defined in extract.py
        from app.pipelines.extract import make_per_sheet_pipeline  # noqa: PLC0415
        self._per_sheet = make_per_sheet_pipeline(llm)

    @component.output_types(plis=list, warnings=list, format_detected=str)
    def run(self, workbook_ctx: Any, relevant_sheets: list) -> dict:
        """Process each sheet through the per-sheet pipeline; return aggregated outputs."""
        all_plis: list = []
        all_warnings: list = []
        format_detected: str | None = None

        for sheet in relevant_sheets:
            out = self._per_sheet.run({
                "planner": {"workbook_ctx": workbook_ctx, "sheet": sheet},
                "plan_validator": {"workbook_ctx": workbook_ctx},
                "layout_hinter": {"workbook_ctx": workbook_ctx, "sheet": sheet},
                "plan_reviewer": {"workbook_ctx": workbook_ctx},
                "field_namer": {"workbook_ctx": workbook_ctx},
                "applier": {"workbook_ctx": workbook_ctx},
            })
            all_plis.extend(out["applier"]["plis"])
            all_warnings.extend(out["applier"]["warnings"])
            if format_detected is None:
                plan = out.get("planner", {}).get("plan")
                if plan is not None:
                    format_detected = plan.pli_mode.value

        return {
            "plis": all_plis,
            "warnings": all_warnings,
            "format_detected": format_detected or "unknown",
        }
