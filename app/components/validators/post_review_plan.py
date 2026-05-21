"""Pipeline-level validator that re-runs structural invariants after PlanReviewer corrections.

Sits between PlanReviewer's output and FieldNamer's input. Asserts that
the corrections the LLM proposed (and the orchestrator applied to
`plan.rows`) didn't break any Tier 1 invariant. If they did, the
finding is recorded as a Warning — the orchestrator may then choose to
discard the corrections.
"""
from __future__ import annotations

from app.components.validators.plan_invariants import validate_invariants
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import SheetPlan, ValidationFinding


def validate_post_review(plan: SheetPlan) -> list[ValidationFinding]:
    """Return all Tier-1 invariant violations introduced by a post-review plan."""
    findings = validate_invariants(plan)
    return [
        _retag(f) for f in findings
        if f.severity == ValidationSeverity.ERROR
    ]


def _retag(f: ValidationFinding) -> ValidationFinding:
    """Re-prefix the check name so operators can see the post-review origin."""
    return ValidationFinding(
        check=f"post_review_plan/{f.check}",
        severity=f.severity,
        message=f.message,
        pli_index=f.pli_index,
        field=f.field,
    )
