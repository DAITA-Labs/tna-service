from app.models.artifacts import SheetPlan, RowSpec, PliBlock, KVAnchor, StageBandSpec
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.services.validation.plan_invariants import validate_invariants


def _plan(rows=None, **kw):
    return SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI, identity_column="B",
        header_rows=[1], rows=rows or [], stage_scope=StageScope.SHEET_LEVEL,
        confidence=1.0, **kw,
    )


def test_reference_integrity_pass():
    rows = [
        RowSpec(idx=2, role=RowRole.ANCHOR, group_id=0),
        RowSpec(idx=3, role=RowRole.CHILD, anchor_idx=2, group_id=0),
    ]
    findings = validate_invariants(_plan(rows=rows))
    assert all(f.severity != "error" for f in findings)


def test_reference_integrity_fail_dangling_anchor_idx():
    rows = [
        RowSpec(idx=3, role=RowRole.CHILD, anchor_idx=99),
    ]
    findings = validate_invariants(_plan(rows=rows))
    assert any(f.check == "reference_integrity" and f.severity == "error"
               for f in findings)


def test_row_uniqueness_fail():
    rows = [
        RowSpec(idx=2, role=RowRole.ANCHOR),
        RowSpec(idx=2, role=RowRole.CHILD, anchor_idx=2),
    ]
    findings = validate_invariants(_plan(rows=rows))
    assert any(f.check == "row_uniqueness" for f in findings)


def test_pli_block_non_overlap_fail():
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.SECTION_PER_PLI,
        pli_blocks=[PliBlock(id=0, bbox=(3, 10)),
                    PliBlock(id=1, bbox=(8, 15))],
        stage_scope=StageScope.PLI_LOCAL, confidence=1.0,
    )
    findings = validate_invariants(plan)
    assert any(f.check == "pli_block_non_overlap" for f in findings)
