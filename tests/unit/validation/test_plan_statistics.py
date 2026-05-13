from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.models.artifacts import SheetPlan, RowSpec
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.services.validation.plan_statistics import validate_statistics


def _ctx(tmp_path, cells):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    for addr, val in cells.items():
        ws[addr] = val
    p = tmp_path / "x.xlsx"; wb.save(p)
    return register_workbook(p)


def test_sequence_match_pass(tmp_path):
    ctx = _ctx(tmp_path, {
        "A1": "S NO", "B1": "IO NO",
        "A2": 1, "B2": 1063,
        "A3": 2, "B3": 1064,
    })
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI, identity_column="B",
        header_rows=[1],
        rows=[RowSpec(idx=2, role=RowRole.ANCHOR, group_id=0),
              RowSpec(idx=3, role=RowRole.ANCHOR, group_id=1)],
        stage_scope=StageScope.SHEET_LEVEL, confidence=1.0,
    )
    findings = validate_statistics(ctx, plan)
    assert all(f.check != "sequence_match" or f.severity != "error"
               for f in findings)


def test_pli_count_sanity_warn(tmp_path):
    """Sheet has many data rows but plan emits zero ANCHORs."""
    ctx = _ctx(tmp_path, {
        "A1": "IO NO", **{f"A{i}": str(1000 + i) for i in range(2, 20)},
    })
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI, identity_column="A",
        rows=[], stage_scope=StageScope.SHEET_LEVEL, confidence=1.0,
    )
    findings = validate_statistics(ctx, plan)
    assert any(f.check == "pli_count_sanity" for f in findings)
