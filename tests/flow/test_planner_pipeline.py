"""Flow test: SheetRowPlanner emits expected SheetPlan per fixture."""
from app.services.planner.plan import SheetRowPlanner
from app.enums.row_role import RowRole
from tests.fixtures.case import fixture_case


@fixture_case(
    "tabular_simple", "tabular_with_totals", "tabular_repeat_header",
    "sheet_per_pli_clean", "row_per_pli_with_merges",
)
def test_planner_emits_expected_plan(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    flow = fixture.expectations("flow")
    if "pli_mode" in flow:
        assert plan.pli_mode.value == flow["pli_mode"]
    if "identity_column" in flow:
        assert plan.identity_column == flow["identity_column"]
    if "anchor_count" in flow:
        anchors = [r for r in plan.rows if r.role is RowRole.ANCHOR]
        assert len(anchors) == flow["anchor_count"]
    if "child_count" in flow:
        children = [r for r in plan.rows if r.role is RowRole.CHILD]
        assert len(children) == flow["child_count"]
    if "kv_anchor_count_per_sheet" in flow:
        assert len(plan.kv_anchors) == flow["kv_anchor_count_per_sheet"][0]
    if "stage_band_count_per_sheet" in flow:
        assert len(plan.stage_bands) == flow["stage_band_count_per_sheet"][0]
    if "header_rows" in flow:
        assert plan.header_rows == flow["header_rows"]
