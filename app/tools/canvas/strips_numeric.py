"""IntStrip + FloatStrip detectors — numeric columns with magnitude tagging.

A column is an IntStrip if ≥80% of its non-blank cells are int-typed.
IntStrip carries a magnitude tag ("small" | "medium" | "large") so that
QuantityComponent can distinguish per-PLI quantity columns (typically
INT_LARGE, range 1–100000) from size-breakdown columns (INT_SMALL,
range 0–10) or short codes (INT_MEDIUM, range 10–1000).

FloatStrip is the float analogue. Both detectors are vertical-only —
the canonical use is per-PLI numeric columns under a tabular header band.
"""
from __future__ import annotations

from typing import Literal

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import FloatStrip, IntStrip, Rect
from app.tools._decorator import tool


_DTYPE_INT = 2
_DTYPE_FLOAT = 3
_DTYPE_BLANK = 0

_MIN_DENSITY = 0.80
_MIN_NON_BLANK = 3

# Magnitude bucket boundaries for IntStrip (used for size vs qty vs code split).
_SMALL_MAX = 10
_MEDIUM_MAX = 1000

Magnitude = Literal["small", "medium", "large"]


@tool("find_int_strips")
def find_int_strips(canvas: GridCanvas,
                    min_density: float = _MIN_DENSITY,
                    min_non_blank: int = _MIN_NON_BLANK,
                    data_row_start: int = 1) -> list[IntStrip]:
    """Detect every vertical IntStrip on the canvas, magnitude-tagged.

    `data_row_start` is 1-indexed: cells in rows < `data_row_start` are
    skipped when computing density. Use it after `resolve_header_band`
    runs so title rows + sub-headers don't pollute the int density of a
    real quantity column.
    """
    return _find_numeric_strips(canvas, _DTYPE_INT, _build_int_strip,
                                 min_density, min_non_blank, data_row_start)


@tool("find_float_strips")
def find_float_strips(canvas: GridCanvas,
                      min_density: float = _MIN_DENSITY,
                      min_non_blank: int = _MIN_NON_BLANK,
                      data_row_start: int = 1) -> list[FloatStrip]:
    """Detect every vertical FloatStrip on the canvas.

    `data_row_start` excludes rows above the header band from the
    density calculation — see `find_int_strips`.
    """
    return _find_numeric_strips(canvas, _DTYPE_FLOAT, _build_float_strip,
                                 min_density, min_non_blank, data_row_start)


def _find_numeric_strips(canvas: GridCanvas,
                         match_dtype: int,
                         build_strip,
                         min_density: float,
                         min_non_blank: int,
                         data_row_start: int) -> list:
    """Generic walker: for each column, compute density of `match_dtype` cells."""
    dtype = canvas.channels.get("dtype")
    if dtype is None:
        return []

    strips: list = []
    for c in range(canvas.n_cols):
        r_start, r_end, density, matched_values = _column_density(
            canvas, c, match_dtype, data_row_start,
        )
        if r_start is None or len(matched_values) < min_non_blank or density < min_density:
            continue
        strip = build_strip(
            rect=Rect(r_start + 1, c + 1, r_end + 1, c + 1),
            density=density,
            matched_values=matched_values,
        )
        strips.append(strip)
    return strips


def _column_density(canvas: GridCanvas, col: int, match_dtype: int,
                    data_row_start: int):
    """Return (r_start, r_end, density, matched_values) for the data span of `col`.

    `density` is the fraction of non-blank cells (in rows ≥ `data_row_start`
    in 1-indexed terms) whose dtype equals `match_dtype`. r_start/r_end
    are 0-indexed; None if no non-blank cells.
    """
    dtype = canvas.channels["dtype"]
    r_start: int | None = None
    r_end: int | None = None
    matched_count = 0
    non_blank_count = 0
    matched_values: list = []
    first_data_row = max(0, data_row_start - 1)   # 1-indexed → 0-indexed

    for r in range(first_data_row, canvas.n_rows):
        dt = dtype[r][col]
        if dt == _DTYPE_BLANK:
            continue
        if r_start is None:
            r_start = r
        r_end = r
        non_blank_count += 1
        if dt == match_dtype:
            matched_count += 1
            matched_values.append(canvas.cell_values[r][col])

    if non_blank_count == 0:
        return None, None, 0.0, []
    return r_start, r_end, matched_count / non_blank_count, matched_values


def _build_int_strip(rect: Rect, density: float, matched_values: list) -> IntStrip:
    """Construct an IntStrip with a magnitude tag derived from value distribution."""
    return IntStrip(
        rect=rect,
        magnitude=_magnitude_of(matched_values),
        density=density,
    )


def _build_float_strip(rect: Rect, density: float, matched_values: list) -> FloatStrip:
    """Construct a FloatStrip — floats don't carry magnitude buckets."""
    return FloatStrip(rect=rect, density=density)


def _magnitude_of(values: list) -> Magnitude:
    """Tag a list of numeric values as small / medium / large by typical magnitude."""
    numeric = [v for v in values if isinstance(v, (int, float))]
    if not numeric:
        return "small"
    avg = sum(abs(v) for v in numeric) / len(numeric)
    if avg <= _SMALL_MAX:
        return "small"
    if avg <= _MEDIUM_MAX:
        return "medium"
    return "large"
