"""Per-row and per-column dtype profile aggregators.

A dtype profile counts the cells of each dtype (blank, date, int, float,
str, formula) across one row or one column. AxisInferrer consumes these
to decide:

- text-dense rows  → header candidates
- numeric-dense rows → data rows
- date-dense columns → stage planned_date column candidates
- int-dense columns → quantity / size / id candidates

The profiles are emitted as `RowDtypeProfile` / `ColDtypeProfile`
records. Densities are not stored — divide by n_cols or n_rows at the
call site to get them.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import ColDtypeProfile, RowDtypeProfile
from app.tools._decorator import tool


_DTYPE_BLANK = 0
_DTYPE_DATE = 1
_DTYPE_INT = 2
_DTYPE_FLOAT = 3
_DTYPE_STR = 4
_DTYPE_FORMULA = 5


@tool("compute_row_dtype_profiles")
def compute_row_dtype_profiles(canvas: GridCanvas) -> list[RowDtypeProfile]:
    """Emit one RowDtypeProfile per row of the canvas."""
    dtype = canvas.channels.get("dtype")
    if dtype is None:
        return []

    profiles: list[RowDtypeProfile] = []
    for r in range(canvas.n_rows):
        counts = _count_dtypes(dtype[r])
        profiles.append(RowDtypeProfile(
            row_idx=r + 1,
            n_cols=canvas.n_cols,
            n_blank=counts[_DTYPE_BLANK],
            n_date=counts[_DTYPE_DATE],
            n_int=counts[_DTYPE_INT],
            n_float=counts[_DTYPE_FLOAT],
            n_str=counts[_DTYPE_STR],
            n_formula=counts[_DTYPE_FORMULA],
        ))
    return profiles


@tool("compute_col_dtype_profiles")
def compute_col_dtype_profiles(canvas: GridCanvas) -> list[ColDtypeProfile]:
    """Emit one ColDtypeProfile per column of the canvas."""
    dtype = canvas.channels.get("dtype")
    if dtype is None:
        return []

    profiles: list[ColDtypeProfile] = []
    for c in range(canvas.n_cols):
        column_values = [dtype[r][c] for r in range(canvas.n_rows)]
        counts = _count_dtypes(column_values)
        profiles.append(ColDtypeProfile(
            col_idx=c + 1,
            n_rows=canvas.n_rows,
            n_blank=counts[_DTYPE_BLANK],
            n_date=counts[_DTYPE_DATE],
            n_int=counts[_DTYPE_INT],
            n_float=counts[_DTYPE_FLOAT],
            n_str=counts[_DTYPE_STR],
            n_formula=counts[_DTYPE_FORMULA],
        ))
    return profiles


def _count_dtypes(values: list[int]) -> dict[int, int]:
    """Tally dtype codes (0-5) across a list of cells; missing codes default to 0."""
    counts = {
        _DTYPE_BLANK: 0,
        _DTYPE_DATE: 0,
        _DTYPE_INT: 0,
        _DTYPE_FLOAT: 0,
        _DTYPE_STR: 0,
        _DTYPE_FORMULA: 0,
    }
    for v in values:
        if v in counts:
            counts[v] += 1
    return counts
