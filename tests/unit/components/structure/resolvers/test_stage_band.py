"""StageBandResolver — pair arenas with their name cells."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import (
    MergeSpan,
    Rect,
    StageArena,
    StageBand,
    StructureBag,
)
from app.components.structure.resolvers.stage_band import resolve_stage_bands


def _canvas_with_label(label: str, label_row: int, label_col: int):
    """Build a minimal canvas with `label` at (label_row, label_col), 1-indexed."""
    n_rows, n_cols = 20, 20
    cells = [[None] * n_cols for _ in range(n_rows)]
    cells[label_row - 1][label_col - 1] = label
    return GridCanvas(
        n_rows=n_rows, n_cols=n_cols, cell_values=cells, channels={}, merge_ranges=set(),
    )


def test_no_arenas_yields_no_bands() -> None:
    """An empty stage_arenas list produces an empty stage_bands list."""
    canvas = _canvas_with_label("ignored", 1, 1)
    bag = StructureBag()
    bands = resolve_stage_bands(canvas, bag)
    assert bands == []
    assert bag.stage_bands == []


def test_horizontal_merge_above_arena_provides_name() -> None:
    """A horizontal MergeSpan above the arena's columns supplies the name."""
    canvas = _canvas_with_label("PPS Submission", label_row=2, label_col=14)
    bag = StructureBag()
    bag.stage_arenas = [StageArena(rect=Rect(4, 14, 43, 14))]
    bag.merge_spans = [MergeSpan(rect=Rect(2, 14, 2, 16), orientation="horizontal")]

    bands = resolve_stage_bands(canvas, bag)
    assert len(bands) == 1
    assert bands[0].name_text == "PPS Submission"
    assert bands[0].name_coord == ("N", 2)


def test_fallback_to_text_above_when_no_merge() -> None:
    """Without a horizontal merge, the closest string cell above is used."""
    canvas = _canvas_with_label("Sewing Start", label_row=3, label_col=20)
    bag = StructureBag()
    bag.stage_arenas = [StageArena(rect=Rect(4, 20, 30, 20))]
    # No merge_spans → fallback path

    bands = resolve_stage_bands(canvas, bag)
    assert len(bands) == 1
    assert bands[0].name_text == "Sewing Start"


def test_arena_with_no_name_skipped() -> None:
    """An arena with no usable name candidate produces no band."""
    canvas = GridCanvas(
        n_rows=10, n_cols=10,
        cell_values=[[None] * 10 for _ in range(10)],
    )
    bag = StructureBag()
    bag.stage_arenas = [StageArena(rect=Rect(4, 5, 6, 5))]

    bands = resolve_stage_bands(canvas, bag)
    assert bands == []


def test_band_carries_arena_rect() -> None:
    """The StageBand's rect equals the source arena's rect."""
    canvas = _canvas_with_label("Cutting", label_row=2, label_col=8)
    bag = StructureBag()
    arena_rect = Rect(4, 8, 30, 8)
    bag.stage_arenas = [StageArena(rect=arena_rect)]
    bag.merge_spans = [MergeSpan(rect=Rect(2, 8, 2, 10), orientation="horizontal")]

    bands = resolve_stage_bands(canvas, bag)
    assert bands[0].rect == arena_rect
