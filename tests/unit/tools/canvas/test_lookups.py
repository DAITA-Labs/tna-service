"""Lookup tools — merged_cells_in_column + column_has_strip."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import DateStrip, IntStrip, Rect, SameLengthStrip
from app.tools._registry import TOOL_REGISTRY
from app.tools.canvas.lookups import column_has_strip, merged_cells_in_column


# ─── merged_cells_in_column ────────────────────────────────────────────────


def _canvas_with_merges(merges):
    return GridCanvas(
        n_rows=10, n_cols=5,
        cell_values=[[None] * 5 for _ in range(10)],
        merge_ranges=set(merges),
    )


def test_no_merges_yields_empty_set() -> None:
    canvas = _canvas_with_merges([])
    assert merged_cells_in_column(canvas, col_idx=1, rows=[3, 4, 5]) == set()


def test_merge_in_target_column_returns_overlapping_cells() -> None:
    """A merge spanning rows 3-4 of column 1 → both cells in the result."""
    canvas = _canvas_with_merges([(3, 1, 4, 1)])
    assert merged_cells_in_column(canvas, col_idx=1, rows=[3, 4, 5]) == {(3, 1), (4, 1)}


def test_merge_in_different_column_returns_empty() -> None:
    canvas = _canvas_with_merges([(3, 2, 4, 2)])  # col 2 merge
    assert merged_cells_in_column(canvas, col_idx=1, rows=[3, 4, 5]) == set()


def test_horizontal_merge_spanning_target_column_returns_only_overlapping_rows() -> None:
    """Merge spans cols 1-3 on row 3 — caller asking about col 1 sees (3, 1)."""
    canvas = _canvas_with_merges([(3, 1, 3, 3)])
    assert merged_cells_in_column(canvas, col_idx=1, rows=[3, 4]) == {(3, 1)}


def test_merge_outside_row_range_is_excluded() -> None:
    """Rows beyond the caller's interest are filtered."""
    canvas = _canvas_with_merges([(3, 1, 10, 1)])
    assert merged_cells_in_column(canvas, col_idx=1, rows=[3, 4]) == {(3, 1), (4, 1)}


def test_tool_registered_under_canonical_name() -> None:
    assert "merged_cells_in_column" in TOOL_REGISTRY.names()


# ─── column_has_strip ──────────────────────────────────────────────────────


def test_no_strips_returns_false() -> None:
    assert column_has_strip([], col_idx=1, rows=[3, 4, 5]) is False


def test_int_strip_overlap_returns_true() -> None:
    strips = [IntStrip(rect=Rect(3, 1, 5, 1), magnitude="medium", density=0.9)]
    assert column_has_strip(strips, col_idx=1, rows=[3, 4, 5]) is True


def test_strip_in_different_column_returns_false() -> None:
    strips = [IntStrip(rect=Rect(3, 2, 5, 2), magnitude="medium", density=0.9)]
    assert column_has_strip(strips, col_idx=1, rows=[3, 4, 5]) is False


def test_strip_outside_data_rows_returns_false() -> None:
    strips = [IntStrip(rect=Rect(20, 1, 25, 1), magnitude="medium", density=0.9)]
    assert column_has_strip(strips, col_idx=1, rows=[3, 4, 5]) is False


def test_works_with_date_strips() -> None:
    """Generic over strip types — any record with a `.rect` attribute is accepted."""
    strips = [DateStrip(rect=Rect(3, 1, 5, 1), orientation="vertical", density=1.0)]
    assert column_has_strip(strips, col_idx=1, rows=[3, 4, 5]) is True


def test_works_with_same_length_strips() -> None:
    strips = [SameLengthStrip(rect=Rect(3, 1, 5, 1), length=10, density=1.0)]
    assert column_has_strip(strips, col_idx=1, rows=[3, 4, 5]) is True


def test_partial_overlap_returns_true() -> None:
    """A strip that only covers one of the caller's data rows is enough."""
    strips = [IntStrip(rect=Rect(3, 1, 3, 1), magnitude="small", density=1.0)]
    assert column_has_strip(strips, col_idx=1, rows=[3, 4, 5]) is True


def test_tool_registered_in_global_registry() -> None:
    assert "column_has_strip" in TOOL_REGISTRY.names()
