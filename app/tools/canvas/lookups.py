"""Column ↔ strip / merge lookups used by field extractors.

Both tools take "where is the candidate column + which data rows are we
walking?" and return a structural answer. Extractors call these to
decide whether a candidate column passes the structure-phase
confirmation gate (any strip type overlap) or to reject a value-cell
position outright (inside a merge range).
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.tools._decorator import tool


@tool("merged_cells_in_column")
def merged_cells_in_column(canvas: GridCanvas,
                              col_idx: int,
                              rows: list[int]) -> set[tuple[int, int]]:
    """Return every (row, col_idx) coord inside a merge range overlapping the column.

    The returned set is cell-level so callers can do O(1) checks per row.
    `merge_ranges` is walked once; the result is intersected with
    `col_idx` + the data-row set so it stays small.
    """
    row_set = set(rows)
    cells: set[tuple[int, int]] = set()
    for r0, c0, r1, c1 in canvas.merge_ranges:
        if c0 <= col_idx <= c1:
            for r in range(r0, r1 + 1):
                if r in row_set:
                    cells.add((r, col_idx))
    return cells


@tool("column_has_strip")
def column_has_strip(strips: list,
                       col_idx: int,
                       rows: list[int]) -> bool:
    """True when any strip's rect overlaps `col_idx` and at least one of `rows`.

    Generic over strip type — pass `bag.int_strips`, `bag.date_strips`,
    `bag.same_length_strips`, `bag.long_text_strips`, etc. The only
    contract is that each element has a `rect: Rect` attribute with
    `r0/c0/r1/c1` ints.
    """
    row_set = set(rows)
    for strip in strips:
        rect = strip.rect
        if rect.c0 <= col_idx <= rect.c1 and any(
            r in row_set for r in range(rect.r0, rect.r1 + 1)
        ):
            return True
    return False
