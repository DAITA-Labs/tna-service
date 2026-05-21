"""PostReviewValidator — pipeline component that re-runs invariants after PlanReviewer."""
from __future__ import annotations

from haystack import component

from app.components._base import Component
from app.components.validators.post_review_plan import validate_post_review
from app.core.log_capture import log_artifact
from app.models.artifacts import SheetPlan, ValidationFinding


@component
class PostReviewValidator(Component):
    """Pipeline component: re-runs invariants after PlanReviewer corrections."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(plan=SheetPlan, findings=list[ValidationFinding])
    def run(self, plan: SheetPlan) -> dict:
        """Return the plan and post-review invariant findings."""
        findings = validate_post_review(plan)
        log_artifact("plan.snapshot_after_reviewer", payload=plan.model_dump())
        return {"plan": plan, "findings": findings}
