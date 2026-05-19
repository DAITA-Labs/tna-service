"""FieldNamer prompt body covers header_labels + stage_columns + sub_columns."""
from app.enums.pli_mode import PliMode
from app.models.artifacts import (
    HeaderLabel, KVAnchor, PliBlock, SheetPlan, StageBandSpec, StageColumn,
)
from app.services.agents.field_namer import _build_user_input


def _stub_ctx(*, max_row: int = 4, max_col: int = 26) -> object:
    class _WS:
        def __init__(self) -> None:
            self.max_row = max_row
            self.max_column = max_col
            self.title = "S"
        def cell(self, row, column):
            class _C:
                value = None
            return _C()
    class _WB:
        def __getitem__(self, _k): return _WS()
    class _Ctx:
        wb = _WB()
    return _Ctx()


def test_row_per_pli_emits_identity_section() -> None:
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_labels=[
            HeaderLabel(raw="IO NO", col="B", row=3),
            HeaderLabel(raw="STYLE", col="F", row=3),
        ],
    )
    body = _build_user_input(_stub_ctx(), {"plan": plan})
    assert "Identity labels detected" in body
    assert "'IO NO'" in body and "(col B)" in body
    assert "'STYLE'" in body and "(col F)" in body


def test_sheet_is_pli_emits_kv_anchor_labels() -> None:
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.SHEET_IS_PLI,
        kv_anchors=[KVAnchor(label_cell="A1", value_cell="B1", field="IO #")],
    )
    body = _build_user_input(_stub_ctx(), {"plan": plan})
    assert "'IO #'" in body


def test_section_per_pli_emits_block_identity() -> None:
    block = PliBlock(
        id=0, bbox=(2, 5),
        identity=[KVAnchor(label_cell="A2", value_cell="B2", field="IO #")],
    )
    plan = SheetPlan(sheet="S", pli_mode=PliMode.SECTION_PER_PLI, pli_blocks=[block])
    body = _build_user_input(_stub_ctx(), {"plan": plan})
    assert "'IO #'" in body


def test_emits_stage_sub_field_section_when_sub_columns_present() -> None:
    band = StageBandSpec(
        name="b", name_cell="U3", sub_header_row=3,
        stage_columns=[StageColumn(name="CUTTING", name_cell="U3", primary_col="U",
                                    sub_columns={"Actual": "V"})],
    )
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_labels=[HeaderLabel(raw="X", col="A", row=3)],
        stage_bands=[band],
    )
    body = _build_user_input(_stub_ctx(), {"plan": plan})
    assert "Stage sub-field labels" in body
    assert "'Actual'" in body
    assert "'CUTTING'" in body
