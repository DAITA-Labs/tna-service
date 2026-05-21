"""PreApplyValidator — pipeline component that confirms plan is ready for apply_plan."""
from __future__ import annotations

from haystack import component

from app.components._base import Component
from app.components.validators.pre_apply_readiness import validate_pre_apply
from app.models.artifacts import SheetPlan, ValidationFinding


@component
class PreApplyValidator(Component):
    """Pipeline component: confirms plan is ready for apply_plan."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(plan=SheetPlan, findings=list[ValidationFinding])
    def run(self, plan: SheetPlan) -> dict:
        """Return the plan and any pre-apply readiness findings."""
        return {"plan": plan, "findings": validate_pre_apply(plan)}
