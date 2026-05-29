"""StageAxisPicker + SubfieldAxisPicker — drop-in regression coverage."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import (
    MergeSpan,
    Rect,
    StageBand,
    StructureBag,
)
from app.components.pickers.stage_axis import StageAxisPicker
from app.components.pickers.subfield_axis import SubfieldAxisPicker


# ── StageAxisPicker ────────────────────────────────────────────────────────


def test_stage_axis_sheet_with_horiz_date_strips_picks_horizontal() -> None:
    out = StageAxisPicker().run(pli_axis="sheet", vert_dates=0, horiz_dates=3)
    assert out["stage_axis"] == "horizontal"
    assert out["confidence"] == 0.9


def test_stage_axis_sheet_with_vert_date_strips_picks_vertical() -> None:
    out = StageAxisPicker().run(pli_axis="sheet", vert_dates=2, horiz_dates=0)
    assert out["stage_axis"] == "vertical"
    assert out["confidence"] == 0.9


def test_stage_axis_sheet_no_strips_picks_none_high_confidence() -> None:
    out = StageAxisPicker().run(pli_axis="sheet", vert_dates=0, horiz_dates=0)
    assert out["stage_axis"] == "none"
    assert out["confidence"] == 0.9


def test_stage_axis_tabular_with_vert_date_strips_picks_horizontal() -> None:
    out = StageAxisPicker().run(pli_axis="vertical", vert_dates=5, horiz_dates=0)
    assert out["stage_axis"] == "horizontal"
    assert out["confidence"] == 0.9


def test_stage_axis_tabular_with_horiz_date_strips_picks_vertical() -> None:
    out = StageAxisPicker().run(pli_axis="sectional", vert_dates=0, horiz_dates=5)
    assert out["stage_axis"] == "vertical"
    assert out["confidence"] == 0.9


def test_stage_axis_tabular_no_strips_picks_none_low_confidence() -> None:
    out = StageAxisPicker().run(pli_axis="vertical", vert_dates=0, horiz_dates=0)
    assert out["stage_axis"] == "none"
    assert out["confidence"] == 0.5


def test_stage_axis_unknown_pli_axis_falls_back_to_unknown() -> None:
    out = StageAxisPicker().run(pli_axis="horizontal", vert_dates=0, horiz_dates=0)
    assert out["stage_axis"] == "unknown"
    assert out["confidence"] == 0.5


# ── SubfieldAxisPicker ─────────────────────────────────────────────────────


def _empty_canvas() -> GridCanvas:
    return GridCanvas(
        n_rows=10, n_cols=10,
        cell_values=[[None] * 10 for _ in range(10)],
        channels={},
    )


def test_subfield_axis_no_stage_bands_picks_implicit() -> None:
    canvas = _empty_canvas()
    bag = StructureBag()
    out = SubfieldAxisPicker().run(canvas=canvas, bag=bag)
    assert out["subfield_axis"] == "implicit"
    assert out["confidence"] == 0.9


def test_subfield_axis_with_overlapping_horiz_merge_picks_horizontal_high() -> None:
    canvas = _empty_canvas()
    bag = StructureBag()
    bag.stage_bands = [
        StageBand(rect=Rect(r0=5, c0=3, r1=10, c1=6),
                   name_coord=("C", 4), name_text="Sewing"),
    ]
    bag.merge_spans = [
        MergeSpan(rect=Rect(r0=3, c0=3, r1=3, c1=6), orientation="horizontal"),
    ]
    out = SubfieldAxisPicker().run(canvas=canvas, bag=bag)
    assert out["subfield_axis"] == "horizontal"
    assert out["confidence"] == 0.9


def test_subfield_axis_band_without_horiz_merge_falls_back_horizontal_low() -> None:
    canvas = _empty_canvas()
    bag = StructureBag()
    bag.stage_bands = [
        StageBand(rect=Rect(r0=5, c0=3, r1=10, c1=6),
                   name_coord=("C", 4), name_text="Sewing"),
    ]
    bag.merge_spans = []
    out = SubfieldAxisPicker().run(canvas=canvas, bag=bag)
    assert out["subfield_axis"] == "horizontal"
    assert out["confidence"] == 0.5
