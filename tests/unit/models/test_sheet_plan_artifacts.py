from app.models.artifacts import RowSpec, KVAnchor, SheetSignals
from app.enums.row_role import RowRole, SubRowRole


def test_row_spec_anchor():
    r = RowSpec(idx=4, role=RowRole.ANCHOR)
    assert r.idx == 4
    assert r.role is RowRole.ANCHOR
    assert r.anchor_idx is None
    assert r.group_id is None
    assert r.sub_row_role is None


def test_row_spec_child_with_anchor():
    r = RowSpec(idx=5, role=RowRole.CHILD, anchor_idx=4, group_id=0)
    assert r.anchor_idx == 4
    assert r.group_id == 0


def test_row_spec_sub_row_role():
    r = RowSpec(idx=3, role=RowRole.CHILD, anchor_idx=2,
                group_id=0, sub_row_role=SubRowRole.ACTION)
    assert r.sub_row_role is SubRowRole.ACTION


def test_kv_anchor():
    kv = KVAnchor(label_cell="A4", value_cell="B4", field="io_number")
    assert kv.label_cell == "A4"
    assert kv.value_cell == "B4"
    assert kv.field == "io_number"


def test_sheet_signals_minimal():
    s = SheetSignals(sheet="X", max_row=10, max_col=5,
                     merges=[], identity_col_candidates=["B"],
                     header_vocab_hits={"B": ["IO NO"]},
                     date_typed_cols=["D"], blank_run_gaps=[])
    assert s.sheet == "X"
    assert s.identity_col_candidates == ["B"]


from app.models.artifacts import StageBandSpec, PliBlock, SheetPlan
from app.enums.pli_mode import PliMode
from app.enums.stage_scope import StageScope


def test_stage_band_spec_minimal():
    sb = StageBandSpec(
        name="Pre-Prod", name_cell="A8", sub_header_row=8,
        sub_rows={"plan": 9, "action": 10},
        stage_cols={"L/D send": "C", "Fit send": "D"},
        layout_mode="tall_sub_rows",
    )
    assert sb.name == "Pre-Prod"
    assert sb.stage_cols["L/D send"] == "C"


def test_pli_block_with_identity_and_bands():
    kv = KVAnchor(label_cell="A4", value_cell="B4", field="io_number")
    sb = StageBandSpec(name="Pre-Prod", name_cell="A8", sub_header_row=8,
                       sub_rows={"plan": 9}, stage_cols={"X": "C"},
                       layout_mode="tall_sub_rows")
    blk = PliBlock(id=0, bbox=(3, 14), identity=[kv], stage_bands=[sb])
    assert blk.bbox == (3, 14)
    assert blk.identity[0].field == "io_number"
    assert blk.stage_bands[0].name == "Pre-Prod"


def test_sheet_plan_row_per_pli_minimal():
    plan = SheetPlan(
        sheet="X", pli_mode=PliMode.ROW_PER_PLI, identity_column="B",
        header_rows=[1], rows=[RowSpec(idx=2, role=RowRole.ANCHOR)],
        stage_scope=StageScope.SHEET_LEVEL, confidence=0.9,
    )
    assert plan.pli_mode is PliMode.ROW_PER_PLI
    assert plan.identity_column == "B"


def test_sheet_plan_sheet_is_pli_minimal():
    plan = SheetPlan(
        sheet="X", pli_mode=PliMode.SHEET_IS_PLI,
        header_rows=[], rows=[],
        kv_anchors=[KVAnchor(label_cell="A4", value_cell="B4", field="io_number")],
        stage_scope=StageScope.SHEET_LEVEL, confidence=0.95,
    )
    assert plan.pli_mode is PliMode.SHEET_IS_PLI
    assert plan.kv_anchors[0].field == "io_number"


from app.models.artifacts import CanonicalNameMap, LayoutHints, PlanVerdict


def test_canonical_name_map():
    nm = CanonicalNameMap(
        field_labels={"Ex-Fty date": "delivery_date",
                      "Job No": "io_number"},
        stage_names={"L/D send": "lab_dip_send"},
    )
    assert nm.field_labels["Ex-Fty date"] == "delivery_date"


def test_layout_hints():
    h = LayoutHints(
        identity_column_suggestion="B",
        mode_suggestion="row_per_pli",
        notes=["B is clearly the IO column"],
    )
    assert h.identity_column_suggestion == "B"


def test_plan_verdict_looks_correct():
    v = PlanVerdict(verdict="looks_correct", row_corrections=[],
                    identity_column_suggestion=None, warnings=[],
                    confidence=0.95)
    assert v.verdict == "looks_correct"


def test_plan_verdict_needs_fix():
    v = PlanVerdict(
        verdict="needs_fix",
        row_corrections=[{"row": 8, "current_role": "total",
                          "suggested_role": "child", "anchor_idx": 4}],
        warnings=["stage band 'CUTTING' may start one column earlier"],
        confidence=0.85,
    )
    assert v.row_corrections[0]["row"] == 8
