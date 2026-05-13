"""Flow test: SheetRowPlanner + apply_plan for SHEET_IS_PLI fixtures."""
from app.services.applier.apply_plan import apply_plan
from app.services.planner.plan import SheetRowPlanner
from app.models.artifacts import CanonicalNameMap
from tests.fixtures.case import fixture_case


@fixture_case("sheet_per_pli_clean")
def test_apply_plan_sheet_is_pli_one_per_sheet(fixture):
    e2e = fixture.expectations("e2e")
    name_map = CanonicalNameMap(**e2e["fake_llm_responses"]["CanonicalNameMap"])
    plis_total = []
    for sheet in fixture.sheets:
        plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=sheet)["plan"]
        plis = apply_plan(fixture.ctx, plan, name_map)
        plis_total.extend(plis)
    assert len(plis_total) == e2e["pli_count"]
    assert [p.io_number for p in plis_total] == e2e["io_numbers"]
