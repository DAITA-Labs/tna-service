"""Flow test: SheetRowPlanner + apply_plan for ROW_PER_PLI fixtures."""
from app.components.applier import apply_plan
from app.components.planner.plan import SheetRowPlanner
from app.models.artifacts import CanonicalNameMap
from tests.fixtures.case import fixture_case


@fixture_case("tabular_simple", "tabular_with_totals", "row_per_pli_with_merges")
def test_apply_plan_row_per_pli_emits_expected_plis(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    name_map = CanonicalNameMap(
        **fixture.expectations("e2e")["fake_llm_responses"]["CanonicalNameMap"]
    )
    plis = apply_plan(fixture.ctx, plan, name_map)
    e2e = fixture.expectations("e2e")
    assert len(plis) == e2e["pli_count"]
    expected_ios = e2e["io_numbers"]
    assert [p.io_number for p in plis] == expected_ios
