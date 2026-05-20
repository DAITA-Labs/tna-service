"""PlanReviewer user input must not contain Python enum repr clutter."""
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.models.artifacts import RowSpec, SheetPlan
from app.services.agents.plan_reviewer import _build_user_input


class _StubGrid:
    cells: list = []


class _StubPeek:
    def __call__(self, ctx, sheet, rows, cols):
        return _StubGrid()


class _StubCtx:
    pass


def test_user_input_uses_json_safe_enum_serialisation(monkeypatch) -> None:
    """Plan dump must NOT contain Python repr like <PliMode.ROW_PER_PLI: 'row_per_pli'>."""
    from app.repositories.workbook_tools._registry import TOOL_REGISTRY
    monkeypatch.setitem(TOOL_REGISTRY._tools, "peek_sheet", _StubPeek())
    plan = SheetPlan(
        sheet="S",
        pli_mode=PliMode.ROW_PER_PLI,
        rows=[RowSpec(idx=2, role=RowRole.ANCHOR)],
    )
    body = _build_user_input(_StubCtx(), {"plan": plan, "findings": []})
    assert "<PliMode" not in body
    assert "<RowRole" not in body
    # The string canonical values should be present.
    assert "row_per_pli" in body
    assert "anchor" in body
