"""AxisInferrer — PliAxis / StageAxis / SubfieldAxis decisions."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import (
    DateStrip,
    KvBlock,
    Rect,
    RepeatingRowGroup,
    StructureBag,
)
from app.components.structure.axis_inferrer import infer_layout_axes


def _canvas(n_rows: int = 30, n_cols: int = 20):
    """Empty canvas with dtype channel (all-blank)."""
    return GridCanvas(
        n_rows=n_rows, n_cols=n_cols,
        cell_values=[[None] * n_cols for _ in range(n_rows)],
        channels={"dtype": [[0] * n_cols for _ in range(n_rows)]},
    )


def test_sheet_pli_axis_for_small_kv_layout() -> None:
    """A small sheet with several kv blocks classifies as PliAxis = sheet."""
    canvas = _canvas(n_rows=20, n_cols=15)  # size = 300, < 600
    bag = StructureBag()
    bag.kv_blocks = [
        KvBlock(label_coord=("A", 4), value_coord=("B", 4), label_text="Job No", value_dtype=2),
        KvBlock(label_coord=("A", 5), value_coord=("B", 5), label_text="Qty", value_dtype=2),
        KvBlock(label_coord=("D", 4), value_coord=("E", 4), label_text="Ex-Fty", value_dtype=1),
        KvBlock(label_coord=("D", 5), value_coord=("E", 5), label_text="Delivery", value_dtype=1),
    ]

    axes = infer_layout_axes(canvas, bag)
    assert axes.pli_axis == "sheet"
    assert axes.confidence["pli"] >= 0.8


def test_sectional_pli_axis_for_repeating_headers() -> None:
    """Many repeating groups + many data rows → PliAxis = sectional."""
    canvas = _canvas(n_rows=200, n_cols=40)
    # Mark every row as data-like by filling dtype with non-blank
    for r in range(200):
        for c in range(10):  # only some cols have data — keeps str density low
            canvas.channels["dtype"][r][c] = 2  # int

    bag = StructureBag()
    bag.repeating_groups = [
        RepeatingRowGroup(row_indices=(1, 20, 40, 60, 80), signature="x"),
        RepeatingRowGroup(row_indices=(2, 21), signature="y"),
        RepeatingRowGroup(row_indices=(3, 22, 42), signature="z"),
    ]

    axes = infer_layout_axes(canvas, bag)
    assert axes.pli_axis == "sectional"


def test_horizontal_stage_axis_for_vertical_date_strips_in_tabular() -> None:
    """ROW_PER_PLI + ≥3 vertical date strips → StageAxis = horizontal."""
    canvas = _canvas(n_rows=50, n_cols=30)
    # Make it vertical PLI: more data rows than cols
    for r in range(50):
        for c in range(5):
            canvas.channels["dtype"][r][c] = 2

    bag = StructureBag()
    bag.date_strips = [
        DateStrip(rect=Rect(4, 10, 30, 10), orientation="vertical", density=1.0),
        DateStrip(rect=Rect(4, 12, 30, 12), orientation="vertical", density=1.0),
        DateStrip(rect=Rect(4, 14, 30, 14), orientation="vertical", density=1.0),
    ]

    axes = infer_layout_axes(canvas, bag)
    assert axes.pli_axis == "vertical"
    assert axes.stage_axis == "horizontal"


def test_horizontal_stage_for_sheet_pli_with_horizontal_strips() -> None:
    """SHEET_IS_PLI + horizontal date strips (banded layout) → StageAxis = horizontal."""
    canvas = _canvas(n_rows=20, n_cols=15)
    bag = StructureBag()
    bag.kv_blocks = [
        KvBlock(label_coord=("A", 4), value_coord=("B", 4), label_text="Job", value_dtype=2),
        KvBlock(label_coord=("A", 5), value_coord=("B", 5), label_text="Qty", value_dtype=2),
        KvBlock(label_coord=("D", 4), value_coord=("E", 4), label_text="Ex", value_dtype=1),
    ]
    bag.date_strips = [
        DateStrip(rect=Rect(9, 3, 9, 15), orientation="horizontal", density=1.0),
        DateStrip(rect=Rect(14, 3, 14, 15), orientation="horizontal", density=1.0),
    ]

    axes = infer_layout_axes(canvas, bag)
    assert axes.pli_axis == "sheet"
    assert axes.stage_axis == "horizontal"


def test_subfield_axis_implicit_with_no_bands() -> None:
    """No StageBands means SubfieldAxis defaults to implicit (high confidence)."""
    canvas = _canvas()
    bag = StructureBag()
    axes = infer_layout_axes(canvas, bag)
    assert axes.subfield_axis == "implicit"


def test_confidence_dict_keys() -> None:
    """confidence dict carries 'pli', 'stage', 'subfield' keys."""
    canvas = _canvas()
    bag = StructureBag()
    axes = infer_layout_axes(canvas, bag)
    assert set(axes.confidence.keys()) == {"pli", "stage", "subfield"}
