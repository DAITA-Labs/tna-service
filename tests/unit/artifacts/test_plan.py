"""CanvasPlan + supporting dataclasses — value, identity, defaults coverage."""
from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from app.artifacts.plan import (
    CanvasPlan,
    FieldLocation,
    MetadataPlan,
    PliKey,
    StageBandPlan,
)
from app.artifacts.structure import KvBlock, Rect
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.pli_axis import PliAxis
from app.enums.read_direction import ReadDirection
from app.enums.subfield_axis import SubfieldAxis


# ── FieldLocation ──────────────────────────────────────────────────────────


def test_field_location_column_mode_row_per_pli() -> None:
    fl = FieldLocation(
        canonical="io_number",
        mode=FieldLocationMode.COLUMN,
        scope=FieldScope.PLI,
        read_direction=ReadDirection.SAME_ROW,
        column=3,
    )
    assert fl.column == 3
    assert fl.row is None
    assert fl.scope == FieldScope.PLI
    assert fl.read_direction == ReadDirection.SAME_ROW


def test_field_location_row_mode_transposed_layout() -> None:
    """COLUMN-axis layouts (transposed) read each PLI's value across a fixed row."""
    fl = FieldLocation(
        canonical="io_number",
        mode=FieldLocationMode.ROW,
        scope=FieldScope.PLI,
        read_direction=ReadDirection.SAME_COLUMN,
        row=5,
    )
    assert fl.mode == FieldLocationMode.ROW
    assert fl.row == 5
    assert fl.column is None


def test_field_location_kv_block_sheet_scoped() -> None:
    kv = KvBlock(label_coord=("A", 4), value_coord=("B", 4),
                  label_text="Job No", value_dtype=2)
    fl = FieldLocation(
        canonical="io_number",
        mode=FieldLocationMode.KV_BLOCK,
        scope=FieldScope.SHEET,
        read_direction=ReadDirection.FIXED,
        kv_block=kv,
    )
    assert fl.kv_block is kv
    assert fl.scope == FieldScope.SHEET


def test_field_location_offset_for_section() -> None:
    fl = FieldLocation(
        canonical="io_number",
        mode=FieldLocationMode.COLUMN,
        scope=FieldScope.GROUP,
        read_direction=ReadDirection.OFFSET,
        column=2,
        delta_row=1,
    )
    assert fl.delta_row == 1
    assert fl.read_direction == ReadDirection.OFFSET


def test_field_location_is_frozen() -> None:
    fl = FieldLocation(
        canonical="io_number",
        mode=FieldLocationMode.MISSING,
        scope=FieldScope.PLI,
        read_direction=ReadDirection.SAME_ROW,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        fl.column = 1  # type: ignore[misc]


# ── StageBandPlan ──────────────────────────────────────────────────────────


def test_stage_band_plan_horizontal_subfields() -> None:
    """ROW_PER_PLI tabular layout — stage band column, subfields as sub-cols."""
    band = StageBandPlan(
        name="Sewing",
        canonical="sewing",
        anchor_coord=(3, 5),
        anchor_rect=Rect(r0=3, c0=5, r1=15, c1=7),
        scope=FieldScope.PLI,
        subfield_axis=SubfieldAxis.HORIZONTAL,
        read_direction=ReadDirection.SAME_ROW,
        subfield_indices={"planned_date": 5, "actual_date": 6, "qty": 7},
    )
    assert band.subfield_indices["planned_date"] == 5
    assert band.read_direction == ReadDirection.SAME_ROW


def test_stage_band_plan_vertical_subfields_sheet_scoped() -> None:
    """SHEET_IS_PLI with stages down rows + subfields as sub-rows below anchor."""
    band = StageBandPlan(
        name="Sewing",
        canonical="sewing",
        anchor_coord=(5, 3),
        anchor_rect=Rect(r0=5, c0=3, r1=8, c1=3),
        scope=FieldScope.SHEET,
        subfield_axis=SubfieldAxis.VERTICAL,
        read_direction=ReadDirection.FIXED,
        subfield_indices={"planned_date": 6, "actual_date": 7, "qty": 8},
    )
    assert band.subfield_axis == SubfieldAxis.VERTICAL
    assert band.scope == FieldScope.SHEET


def test_stage_band_plan_implicit_subfields() -> None:
    band = StageBandPlan(
        name="Sewing",
        canonical=None,
        anchor_coord=(3, 5),
        anchor_rect=Rect(r0=3, c0=5, r1=3, c1=5),
        scope=FieldScope.PLI,
        subfield_axis=SubfieldAxis.IMPLICIT,
        read_direction=ReadDirection.SAME_ROW,
    )
    assert band.subfield_indices == {}


# ── MetadataPlan ──────────────────────────────────────────────────────────


def test_metadata_plan_column_default_pli_scope() -> None:
    mp = MetadataPlan(header_text="Comments", column=11)
    assert mp.mode == FieldLocationMode.COLUMN
    assert mp.scope == FieldScope.PLI
    assert mp.read_direction == ReadDirection.SAME_ROW
    assert mp.column == 11


def test_metadata_plan_row_shape_for_transposed() -> None:
    mp = MetadataPlan(
        header_text="Comments",
        mode=FieldLocationMode.ROW,
        scope=FieldScope.PLI,
        read_direction=ReadDirection.SAME_COLUMN,
        row=5,
    )
    assert mp.mode == FieldLocationMode.ROW
    assert mp.row == 5


def test_metadata_plan_kv_sheet_scoped() -> None:
    kv = KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                  label_text="Buyer", value_dtype=4)
    mp = MetadataPlan(
        header_text="Buyer",
        canonical="buyer",
        mode=FieldLocationMode.KV_BLOCK,
        scope=FieldScope.SHEET,
        read_direction=ReadDirection.FIXED,
        kv_block=kv,
    )
    assert mp.kv_block is kv
    assert mp.scope == FieldScope.SHEET


def test_metadata_plan_kv_group_scoped_section_offset() -> None:
    kv = KvBlock(label_coord=("A", 4), value_coord=("B", 4),
                  label_text="Season", value_dtype=4)
    mp = MetadataPlan(
        header_text="Season",
        canonical="season",
        mode=FieldLocationMode.KV_BLOCK,
        scope=FieldScope.GROUP,
        read_direction=ReadDirection.OFFSET,
        kv_block=kv,
        delta_row=0,
    )
    assert mp.scope == FieldScope.GROUP
    assert mp.read_direction == ReadDirection.OFFSET


# ── CanvasPlan ─────────────────────────────────────────────────────────────


def test_canvas_plan_minimum_required_fields() -> None:
    plan = CanvasPlan(
        cluster_id="c1",
        anchor_sheet_name="TNA",
        pli_axis=PliAxis.ROW,
    )
    assert plan.cluster_id == "c1"
    assert plan.pli_axis == PliAxis.ROW
    assert plan.pli_rows == []
    assert plan.field_locations == {}
    assert plan.stage_bands == []
    assert plan.metadata_entries == []
    assert plan.confidence == 0.0


def test_canvas_plan_populated_with_metadata_entries() -> None:
    plan = CanvasPlan(
        cluster_id="c1",
        anchor_sheet_name="TNA",
        pli_axis=PliAxis.ROW,
        pli_rows=[4, 5, 6],
        field_locations={
            "io_number": FieldLocation(
                canonical="io_number",
                mode=FieldLocationMode.COLUMN,
                scope=FieldScope.PLI,
                read_direction=ReadDirection.SAME_ROW,
                column=1,
            ),
        },
        metadata_entries=[
            MetadataPlan(header_text="Comments", column=11),
        ],
        confidence=0.92,
    )
    assert plan.pli_rows == [4, 5, 6]
    assert plan.field_locations["io_number"].column == 1
    assert plan.metadata_entries[0].header_text == "Comments"


# ── PliKey ─────────────────────────────────────────────────────────────────


def test_pli_key_is_hashable() -> None:
    k = PliKey(
        io_number="IO-1", style_code="S-1",
        color_code=None, fabric_code=None, quantity=100,
        ex_fty_date=None, shipment_date=date(2026, 1, 1), delivery_date=None,
    )
    s = {k}
    assert k in s


def test_pli_key_equality_is_structural() -> None:
    k1 = PliKey(io_number="A", style_code="B", color_code=None, fabric_code=None,
                quantity=500,
                ex_fty_date=None, shipment_date=None, delivery_date=date(2026, 1, 1))
    k2 = PliKey(io_number="A", style_code="B", color_code=None, fabric_code=None,
                quantity=500,
                ex_fty_date=None, shipment_date=None, delivery_date=date(2026, 1, 1))
    assert k1 == k2
    assert hash(k1) == hash(k2)


def test_pli_key_diff_quantity_not_equal() -> None:
    """Quantity is part of identity — different quantities = different PLIs."""
    k1 = PliKey(io_number="A", style_code="B", color_code=None, fabric_code=None,
                quantity=100,
                ex_fty_date=None, shipment_date=None, delivery_date=date(2026, 1, 1))
    k2 = PliKey(io_number="A", style_code="B", color_code=None, fabric_code=None,
                quantity=200,
                ex_fty_date=None, shipment_date=None, delivery_date=date(2026, 1, 1))
    assert k1 != k2


# ── Package re-exports ─────────────────────────────────────────────────────


def test_plan_artifacts_reexported_from_package() -> None:
    from app.artifacts import (
        CanvasPlan as Reexp_CanvasPlan,
        FieldLocation as Reexp_FieldLocation,
        MetadataPlan as Reexp_MetadataPlan,
        PliKey as Reexp_PliKey,
        StageBandPlan as Reexp_StageBandPlan,
    )

    assert Reexp_CanvasPlan      is CanvasPlan
    assert Reexp_FieldLocation   is FieldLocation
    assert Reexp_MetadataPlan    is MetadataPlan
    assert Reexp_PliKey          is PliKey
    assert Reexp_StageBandPlan   is StageBandPlan


# ── New enum re-exports (FieldScope, ReadDirection, ROW mode) ──────────────


def test_field_scope_reachable_from_app_enums() -> None:
    from app.enums import FieldScope as Reexp
    from app.enums.field_scope import FieldScope as Canonical
    assert Reexp is Canonical


def test_read_direction_reachable_from_app_enums() -> None:
    from app.enums import ReadDirection as Reexp
    from app.enums.read_direction import ReadDirection as Canonical
    assert Reexp is Canonical


def test_legacy_field_scope_import_path_preserved() -> None:
    """`from app.specs.enums import FieldScope` keeps working via shim."""
    from app.enums.field_scope import FieldScope as Canonical
    from app.specs.enums import FieldScope as Legacy
    assert Canonical is Legacy


def test_legacy_read_direction_import_path_preserved() -> None:
    from app.enums.read_direction import ReadDirection as Canonical
    from app.specs.enums import ReadDirection as Legacy
    assert Canonical is Legacy


def test_field_location_mode_has_row_value() -> None:
    """ROW joins COLUMN / KV_BLOCK / MISSING so metadata + transposed identifiers
    have a physical shape."""
    assert FieldLocationMode.ROW.value == "row"
    assert {m.value for m in FieldLocationMode} == {"column", "row", "kv_block", "missing"}
