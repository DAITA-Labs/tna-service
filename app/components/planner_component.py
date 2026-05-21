"""Planner — pipeline component that wraps SheetRowPlanner."""
from __future__ import annotations

from typing import Any

from haystack import component

from app.components._base import Component
from app.components.planner.plan import SheetRowPlanner
from app.models.artifacts import SheetPlan


@component
class Planner(Component):
    """Pipeline component that emits a SheetPlan for one sheet."""

    def __init__(self) -> None:
        Component.__init__(self)
        self._planner = SheetRowPlanner()

    @component.output_types(plan=SheetPlan)
    def run(self, workbook_ctx: Any, sheet: str) -> dict:
        """Run the deterministic SheetRowPlanner and return the plan."""
        plan: SheetPlan = self._planner.run(workbook_ctx=workbook_ctx, sheet=sheet)["plan"]
        return {"plan": plan}
