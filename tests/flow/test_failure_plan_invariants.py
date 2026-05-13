# tests/flow/test_failure_plan_invariants.py
"""Flow failure test: synthetic SheetPlan with dangling anchor_idx triggers
reference_integrity ERROR from validate_invariants."""
import importlib
from app.services.validation.plan_invariants import validate_invariants
from app.enums.validation_severity import ValidationSeverity
from tests.fixtures.case import fixture_case


@fixture_case("plan_invariant_dangling_anchor")
def test_plan_invariant_detects_dangling_anchor(fixture):
    # Synthetic-plan fixtures expose build_plan(); load the module to call it.
    mod = importlib.import_module(f"tests.fixtures.builders.{fixture.name}")
    plan = mod.build_plan()
    findings = validate_invariants(plan)
    expected_violation = fixture.failure_expectations()["expected_invariant_violation"]
    errors = [f for f in findings if f.severity == ValidationSeverity.ERROR]
    assert any(f.check == expected_violation for f in errors)
