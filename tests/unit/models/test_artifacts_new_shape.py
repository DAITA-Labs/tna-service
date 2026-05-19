"""Shape-only tests for the new bridge-artifact fields added in Phase 1."""
from app.models.artifacts import (
    CanonicalNameMap,
    HeaderLabel,
    KVAnchor,
    SheetPlan,
    StageBandSpec,
    StageColumn,
)
from app.enums.pli_mode import PliMode


def test_header_label_validates() -> None:
    hl = HeaderLabel(raw="IO NO", col="B", row=3)
    assert hl.raw == "IO NO"
    assert hl.col == "B"
    assert hl.row == 3
    assert hl.confidence == 0.85


def test_stage_column_accepts_sub_columns() -> None:
    sc = StageColumn(
        name="CUTTING",
        name_cell="U3",
        primary_col="U",
        sub_columns={"Actual": "V", "Remarks": "W"},
    )
    assert sc.sub_columns["Actual"] == "V"


def test_kv_anchor_default_confidence() -> None:
    kv = KVAnchor(label_cell="A1", value_cell="B1", field="io_number")
    assert kv.confidence == 0.95


def test_stage_band_spec_default_stage_columns_empty() -> None:
    band = StageBandSpec(name="band", name_cell="A1", sub_header_row=2)
    assert band.stage_columns == []
    assert band.stage_cols == {}


def test_sheet_plan_default_header_labels_empty() -> None:
    plan = SheetPlan(sheet="S", pli_mode=PliMode.ROW_PER_PLI)
    assert plan.header_labels == []


def test_canonical_name_map_optional_confidence_dicts() -> None:
    nm = CanonicalNameMap()
    assert nm.field_confidence == {}
    assert nm.stage_confidence == {}
    assert nm.stage_subfield_labels == {}
