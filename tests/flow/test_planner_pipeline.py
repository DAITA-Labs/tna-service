"""Flow test: SheetRowPlanner emits expected SheetPlan per fixture."""
from app.services.planner.plan import SheetRowPlanner
from app.enums.row_role import RowRole
from tests.fixtures.case import fixture_case


@fixture_case(
    "tabular_simple", "tabular_with_totals", "tabular_repeat_header",
    "sheet_per_pli_clean", "row_per_pli_with_merges",
    "row_per_pli_wide_single_row_strip", "row_per_pli_wide_two_row_strip",
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
    if "header_labels_count_min" in flow:
        assert len(plan.header_labels) >= flow["header_labels_count_min"], (
            f"header_labels count {len(plan.header_labels)} < {flow['header_labels_count_min']}"
        )
    if "stage_bands_count" in flow:
        assert len(plan.stage_bands) == flow["stage_bands_count"], (
            f"stage_bands count {len(plan.stage_bands)} != {flow['stage_bands_count']}"
        )
    if "stage_columns_min" in flow:
        total = sum(len(b.stage_columns) for b in plan.stage_bands)
        assert total >= flow["stage_columns_min"], (
            f"total stage_columns {total} < {flow['stage_columns_min']}"
        )
    if "first_stage_column" in flow:
        spec = flow["first_stage_column"]
        assert plan.stage_bands, "first_stage_column spec requires at least one stage band"
        assert plan.stage_bands[0].stage_columns, (
            "first_stage_column spec requires at least one stage column in first band"
        )
        sc = plan.stage_bands[0].stage_columns[0]
        if "name" in spec:
            assert sc.name == spec["name"], (
                f"first stage column name {sc.name!r} != {spec['name']!r}"
            )
        if "primary_col" in spec:
            assert sc.primary_col == spec["primary_col"], (
                f"first stage column primary_col {sc.primary_col!r} != {spec['primary_col']!r}"
            )
        if "sub_columns_keys" in spec:
            assert set(sc.sub_columns.keys()) >= set(spec["sub_columns_keys"]), (
                f"first stage column sub_columns keys {set(sc.sub_columns.keys())} "
                f"missing {set(spec['sub_columns_keys']) - set(sc.sub_columns.keys())}"
            )
