"""Pipeline-level validator that re-runs structural + statistical checks after PlanReviewer corrections.

Sits between PlanReviewer's output and FieldNamer's input. Re-runs the
Tier-1 invariant suite on the post-review plan and returns every finding
(both ERROR and WARN), each retagged with a ``post_review_plan/`` prefix
so operators can see which checkpoint produced it. The orchestrator
decides what to do with each severity — typically: errors discard the
corrections, warnings just attach to the result.
"""
from __future__ import annotations

from app.components.validators.plan_invariants import validate_invariants
from app.models.artifacts import SheetPlan, ValidationFinding


def validate_post_review(plan: SheetPlan) -> list[ValidationFinding]:
    """Return all Tier-1 findings (errors + warnings) for the post-review plan."""
    return [_retag(f) for f in validate_invariants(plan)]


def _retag(f: ValidationFinding) -> ValidationFinding:
    """Re-prefix the check name so operators can see the post-review origin."""
    return ValidationFinding(
        check=f"post_review_plan/{f.check}",
        severity=f.severity,
        message=f.message,
        pli_index=f.pli_index,
        field=f.field,
    )
