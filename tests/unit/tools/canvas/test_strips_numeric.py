"""IntStrip + FloatStrip detection — magnitude-tagged numeric columns."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.artifacts.structure import FloatStrip, IntStrip
from app.tools.canvas.build import build_canvas
from app.tools.canvas.strips_numeric import find_float_strips, find_int_strips


DATASET = Path(__file__).resolve().parents[4] / "dataset"


@pytest.fixture
def dkn_canvas():
    """DKN has a quantity column (large ints) + S.No (small ints)."""
    wb = load_workbook(DATASET / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
                       data_only=True)
    return build_canvas(wb.active)


def test_int_strips_returned_as_typed_records(dkn_canvas) -> None:
    """find_int_strips returns IntStrip records with rect + magnitude + density."""
    strips = find_int_strips(dkn_canvas)
    assert isinstance(strips, list)
    assert all(isinstance(s, IntStrip) for s in strips)
    for s in strips:
        assert s.magnitude in ("small", "medium", "large")
        assert 0.0 <= s.density <= 1.0


def test_int_strip_magnitude_values_valid(dkn_canvas) -> None:
    """Every magnitude on a detected IntStrip is one of the three valid tags."""
    strips = find_int_strips(dkn_canvas)
    magnitudes = {s.magnitude for s in strips}
    assert magnitudes.issubset({"small", "medium", "large"})


def test_int_strip_magnitude_tagging_logic() -> None:
    """Magnitude tagging follows the documented buckets."""
    from app.tools.canvas.strips_numeric import _magnitude_of

    assert _magnitude_of([1, 2, 3]) == "small"          # ≤ 10
    assert _magnitude_of([50, 100, 200]) == "medium"    # > 10, ≤ 1000
    assert _magnitude_of([5000, 10000]) == "large"      # > 1000
    assert _magnitude_of([]) == "small"                 # default for empty


def test_float_strips_separate_from_int_strips(dkn_canvas) -> None:
    """FloatStrip records do not overlap with IntStrip — different dtypes."""
    int_strips = find_int_strips(dkn_canvas)
    float_strips = find_float_strips(dkn_canvas)

    int_cols = {s.rect.c0 for s in int_strips}
    float_cols = {s.rect.c0 for s in float_strips}
    # A column whose dtype is mostly int won't be classified as float — they're
    # mutually exclusive in dtype space.
    assert int_cols.isdisjoint(float_cols)


def test_min_density_filters_mixed_columns(dkn_canvas) -> None:
    """Raising min_density should not increase the number of strips."""
    lax = find_int_strips(dkn_canvas, min_density=0.5)
    strict = find_int_strips(dkn_canvas, min_density=0.99)
    assert len(strict) <= len(lax)


def test_min_non_blank_drops_tiny_columns(dkn_canvas) -> None:
    """Demanding many non-blank cells filters out single-cell int columns."""
    permissive = find_int_strips(dkn_canvas, min_non_blank=1)
    strict = find_int_strips(dkn_canvas, min_non_blank=10)
    assert len(strict) <= len(permissive)


def test_tools_registered() -> None:
    from app.tools._registry import TOOL_REGISTRY

    names = TOOL_REGISTRY.names()
    assert "find_int_strips" in names
    assert "find_float_strips" in names


# ── data_row_start excludes header rows from density ──────────────────────


def _synthetic_canvas(cells: list[list]):
    """Build a GridCanvas + dtype channel from a 2-D cell array, no openpyxl."""
    from app.artifacts.canvas import GridCanvas

    n_rows, n_cols = len(cells), len(cells[0])
    dtype = [[0] * n_cols for _ in range(n_rows)]
    for r in range(n_rows):
        for c in range(n_cols):
            v = cells[r][c]
            if v is None or v == "":
                dtype[r][c] = 0
            elif isinstance(v, bool):
                dtype[r][c] = 2
            elif isinstance(v, int):
                dtype[r][c] = 2
            elif isinstance(v, float):
                dtype[r][c] = 3
            else:
                dtype[r][c] = 4
    return GridCanvas(
        n_rows=n_rows, n_cols=n_cols, cell_values=cells,
        channels={"dtype": dtype},
    )


def test_int_strip_rejected_when_headers_drag_density_below_threshold() -> None:
    """Column with 3 header strings + 5 ints is 62% int — below 80% default."""
    cells = [
        ["Title"], ["Quantity"], ["Qty"],
        [498], [821], [553], [694], [605],
    ]
    canvas = _synthetic_canvas(cells)
    assert find_int_strips(canvas) == []


def test_int_strip_detected_when_data_row_start_skips_headers() -> None:
    """Same canvas, `data_row_start=4` makes the column 100% int."""
    cells = [
        ["Title"], ["Quantity"], ["Qty"],
        [498], [821], [553], [694], [605],
    ]
    canvas = _synthetic_canvas(cells)
    strips = find_int_strips(canvas, data_row_start=4)
    assert len(strips) == 1
    assert strips[0].density == 1.0


def test_data_row_start_works_for_float_strips() -> None:
    cells = [
        ["Header"], ["Sub-header"],
        [1.5], [2.0], [3.25], [4.0],
    ]
    canvas = _synthetic_canvas(cells)
    assert find_float_strips(canvas) == []
    strips = find_float_strips(canvas, data_row_start=3)
    assert len(strips) == 1
    assert strips[0].density == 1.0


def test_data_row_start_default_is_no_op() -> None:
    """Default `data_row_start=1` includes the whole sheet."""
    cells = [[1], [2], [3], [4], [5]]
    canvas = _synthetic_canvas(cells)
    assert len(find_int_strips(canvas)) == 1
