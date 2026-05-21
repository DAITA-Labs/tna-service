# tests/flow/test_failure_planner_ambiguity.py
"""Flow failure test: planner ambiguity — no identity column candidates."""
from app.components.planner.plan import SheetRowPlanner
from app.components.validators.plan_statistics import validate_statistics
from tests.fixtures.case import fixture_case


@fixture_case("tabular_corrupt_no_identity_col")
def test_planner_ambiguity_flags_pli_count_sanity(fixture):
    assert fixture.is_failure_case()
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    findings = validate_statistics(fixture.ctx, plan)
    warnings = [f.check for f in findings]
    expected_check = fixture.failure_expectations()["expected_warning_check"]
    assert expected_check in warnings
