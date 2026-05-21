# tests/flow/test_failure_data_anomalies.py
"""Flow failure test: stage band with mostly non-date cells triggers
date_band_density warning from validate_statistics."""
from app.components.planner.plan import SheetRowPlanner
from app.components.validators.plan_statistics import validate_statistics
from tests.fixtures.case import fixture_case


@fixture_case("stage_band_low_date_density")
def test_low_date_density_flags_warning(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    findings = validate_statistics(fixture.ctx, plan)
    expected_check = fixture.failure_expectations()["expected_warning_check"]
    checks = [f.check for f in findings]
    assert expected_check in checks
