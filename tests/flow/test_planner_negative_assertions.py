"""Negative assertions: for each positive fixture, confirm the planner does
NOT produce features that don't apply (mode differentiation, etc.).

These tests complement the positive `test_planner_pipeline.py` — together
they pin both what the planner emits AND what it deliberately doesn't emit
for each layout family."""
from app.services.planner.plan import SheetRowPlanner
from tests.fixtures.case import fixture_case


_POSITIVE_FIXTURES = (
    "tabular_simple",
    "tabular_with_totals",
    "tabular_repeat_header",
    "sheet_per_pli_clean",
    "row_per_pli_with_merges",
    "row_per_pli_wide_single_row_strip",
    "row_per_pli_wide_two_row_strip",
)


@fixture_case(*_POSITIVE_FIXTURES)
def test_planner_negative_assertions(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    flow = fixture.expectations("flow")
    must_not = flow.get("must_not")
    if must_not is None:
        return  # fixture opted out

    if "pli_mode_in" in must_not:
        assert plan.pli_mode.value not in must_not["pli_mode_in"], (
            f"Fixture {fixture.name!r} unexpectedly classified as {plan.pli_mode.value}"
        )
    if must_not.get("has_kv_anchors") is False:
        assert len(plan.kv_anchors) == 0, (
            f"Fixture {fixture.name!r} unexpectedly emitted {len(plan.kv_anchors)} kv_anchors"
        )
    if must_not.get("has_pli_blocks") is False:
        assert len(plan.pli_blocks) == 0, (
            f"Fixture {fixture.name!r} unexpectedly emitted {len(plan.pli_blocks)} pli_blocks"
        )
    if must_not.get("has_rows") is False:
        assert len(plan.rows) == 0, (
            f"Fixture {fixture.name!r} (SHEET_IS_PLI) unexpectedly emitted {len(plan.rows)} rows"
        )
