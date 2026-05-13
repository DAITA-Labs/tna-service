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
