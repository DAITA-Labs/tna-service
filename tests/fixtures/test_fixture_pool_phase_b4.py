from tests.fixtures.case import fixture_case
from app.models.artifacts import SheetPlan


@fixture_case("plan_invariant_dangling_anchor")
def test_synthetic_plan_loads(fixture):
    # synthetic plan fixture has no xlsx_path
    assert fixture.xlsx_path is None
    assert fixture.ctx is None
    assert fixture.is_failure_case()


@fixture_case("apply_name_map_missing_required", "agent_returns_invalid_json")
def test_remaining_failure_fixtures_load(fixture):
    assert fixture.is_failure_case()
