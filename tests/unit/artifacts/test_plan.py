"""CanvasPlan + supporting dataclasses — value, identity, defaults coverage."""
from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from app.artifacts.plan import (
    CanvasPlan,
    FieldLocation,
    MetadataColumn,
    PliKey,
    StageBandPlan,
)
from app.artifacts.structure import KvBlock
from app.enums.field_location_mode import FieldLocationMode
from app.enums.pli_axis import PliAxis


# ── FieldLocation ──────────────────────────────────────────────────────────


def test_field_location_column_mode() -> None:
    fl = FieldLocation(canonical="io_number", mode=FieldLocationMode.COLUMN, column=3)
    assert fl.canonical == "io_number"
    assert fl.mode == FieldLocationMode.COLUMN
    assert fl.column == 3
    assert fl.kv_block is None
    assert fl.verdicts == []


def test_field_location_kv_block_mode() -> None:
    kv = KvBlock(label_coord=("A", 4), value_coord=("B", 4),
                  label_text="Job No", value_dtype=2)
    fl = FieldLocation(canonical="io_number", mode=FieldLocationMode.KV_BLOCK, kv_block=kv)
    assert fl.mode == FieldLocationMode.KV_BLOCK
    assert fl.kv_block is kv
    assert fl.column is None


def test_field_location_is_frozen() -> None:
    fl = FieldLocation(canonical="io_number", mode=FieldLocationMode.MISSING)
    with pytest.raises(dataclasses.FrozenInstanceError):
        fl.column = 1  # type: ignore[misc]


# ── StageBandPlan ──────────────────────────────────────────────────────────


def test_stage_band_plan_defaults() -> None:
    band = StageBandPlan(name="Sewing", canonical=None, column_range=(5, 8))
    assert band.subfield_cols == {}
    assert band.score == 0.0
    assert band.verdicts == []


def test_stage_band_plan_with_subfields() -> None:
    band = StageBandPlan(
        name="Sewing", canonical="sewing",
        column_range=(5, 8),
        subfield_cols={"planned_date": 5, "actual_date": 6, "qty": 7},
    )
    assert band.subfield_cols["planned_date"] == 5


# ── MetadataColumn ─────────────────────────────────────────────────────────


def test_metadata_column_keeps_raw_header_text() -> None:
    mc = MetadataColumn(column=12, header_text="Buyer Comments")
    assert mc.header_text == "Buyer Comments"
    assert mc.canonical is None


def test_metadata_column_canonical_when_matched() -> None:
    mc = MetadataColumn(column=12, header_text="Buyer", canonical="buyer")
    assert mc.canonical == "buyer"


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
    assert plan.metadata_columns == []
    assert plan.confidence == 0.0


def test_canvas_plan_populated() -> None:
    plan = CanvasPlan(
        cluster_id="c1",
        anchor_sheet_name="TNA",
        pli_axis=PliAxis.ROW,
        pli_rows=[4, 5, 6],
        field_locations={
            "io_number": FieldLocation(
                canonical="io_number", mode=FieldLocationMode.COLUMN, column=1,
            ),
        },
        confidence=0.92,
    )
    assert plan.pli_rows == [4, 5, 6]
    assert plan.field_locations["io_number"].column == 1


# ── PliKey ─────────────────────────────────────────────────────────────────


def test_pli_key_is_hashable() -> None:
    k = PliKey(
        io_number="IO-1", style_code="S-1",
        color_code=None, fabric_code=None,
        ex_fty_date=None, shipment_date=date(2026, 1, 1), delivery_date=None,
    )
    s = {k}
    assert k in s


def test_pli_key_equality_is_structural() -> None:
    k1 = PliKey(io_number="A", style_code="B", color_code=None, fabric_code=None,
                ex_fty_date=None, shipment_date=None, delivery_date=date(2026, 1, 1))
    k2 = PliKey(io_number="A", style_code="B", color_code=None, fabric_code=None,
                ex_fty_date=None, shipment_date=None, delivery_date=date(2026, 1, 1))
    assert k1 == k2
    assert hash(k1) == hash(k2)


def test_pli_key_diff_delivery_dates_not_equal() -> None:
    k1 = PliKey(io_number="A", style_code="B", color_code=None, fabric_code=None,
                ex_fty_date=None, shipment_date=None, delivery_date=date(2026, 1, 1))
    k2 = PliKey(io_number="A", style_code="B", color_code=None, fabric_code=None,
                ex_fty_date=None, shipment_date=None, delivery_date=date(2026, 2, 1))
    assert k1 != k2


# ── Package re-exports ─────────────────────────────────────────────────────


def test_plan_artifacts_reexported_from_package() -> None:
    from app.artifacts import (
        CanvasPlan as Reexp_CanvasPlan,
        FieldLocation as Reexp_FieldLocation,
        MetadataColumn as Reexp_MetadataColumn,
        PliKey as Reexp_PliKey,
        StageBandPlan as Reexp_StageBandPlan,
    )

    assert Reexp_CanvasPlan      is CanvasPlan
    assert Reexp_FieldLocation   is FieldLocation
    assert Reexp_MetadataColumn  is MetadataColumn
    assert Reexp_PliKey          is PliKey
    assert Reexp_StageBandPlan   is StageBandPlan
