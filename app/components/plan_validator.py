"""PlanValidator — pipeline component that runs Tier-1 + Tier-2 validation."""
from __future__ import annotations

from typing import Any

from haystack import component

from app.components._base import Component
from app.components.validators.plan_invariants import validate_invariants
from app.components.validators.plan_statistics import validate_statistics
from app.core.log_capture import log_artifact
from app.models.artifacts import SheetPlan, ValidationFinding


@component
class PlanValidator(Component):
    """Pipeline component that runs Tier-1 and Tier-2 validation; emits findings + plan."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(plan=SheetPlan, findings=list[ValidationFinding])
    def run(self, workbook_ctx: Any, plan: SheetPlan) -> dict:
        """Run invariant and statistics validators and return all findings."""
        t1 = validate_invariants(plan)
        t2 = validate_statistics(workbook_ctx, plan)
        log_artifact("plan.snapshot_after_planner", payload=plan.model_dump())
        return {"plan": plan, "findings": t1 + t2}
