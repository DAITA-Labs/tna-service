"""find_around — neighbourhood primitives over an openpyxl sheet.

Two tools:

  find_around_cell(grid, "B4")
      Returns the 8 cells surrounding "B4" plus the cell itself, each as a
      CellInfo carrying merge-resolved value, dtype, style hints, and merge
      anchor metadata.

  find_around_range(grid, row_range, col_range)
      Returns the frame around a rectangular range — cells directly above /
      below / left / right of the range, plus the four corners, plus a
      summary of cell densities inside the range.

Both consume a `grid` dict built by `build_rich_grid(sheet)`, which is a
companion helper that walks an openpyxl sheet once and produces a
`{(row, col_letter): CellInfo}` map with merges resolved.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from openpyxl.cell.cell import MergedCell
from openpyxl.utils import column_index_from_string, get_column_letter

from app.tools._decorator import tool


# =============================================================================
# Data models
# =============================================================================

@dataclass
class CellInfo:
    """Rich info for one cell."""
    coord:          str
    row:            int
    col:            str                  # column letter
    value:          Any                  # merge-resolved value
    raw_value:      Any                  # value at this exact cell (None if merged continuation)
    dtype:          str                  # "date" | "int" | "float" | "str" | "blank" | "formula"
    is_merged:      bool                 # True if this cell is inside a merge range
    is_merge_anchor:bool                 # True if this is the top-left of a merge
    merge_anchor:   str | None        # the top-left coord (e.g., "B2")
    merge_range:    tuple | None      # (min_row, min_col, max_row, max_col) if merged
    merge_size:     tuple | None      # (rows, cols) span of the merge if merged
    is_bold:        bool
    fill_color:     str | None        # hex like "FFCCCC"
    has_border:     bool


@dataclass
class CellNeighbourhood:
    """The 8 neighbours of a centre cell + the centre itself."""
    center:       CellInfo
    above:        CellInfo | None
    below:        CellInfo | None
    left:         CellInfo | None
    right:        CellInfo | None
    above_left:   CellInfo | None
    above_right:  CellInfo | None
    below_left:   CellInfo | None
    below_right:  CellInfo | None

    def as_grid_str(self) -> str:
        """Render the 3x3 neighbourhood as a text grid."""
        def fmt(c):
            if c is None: return "(out)"
            if c.value in (None, ""): return f"({c.coord} blank)"
            v = str(c.value)
            if len(v) > 22: v = v[:21] + "…"
            tag = ""
            if c.is_merge_anchor: tag += "🔝"
            elif c.is_merged: tag += "🟪"
            return f"{c.coord}={v}{tag}"
        rows = [
            [self.above_left, self.above, self.above_right],
            [self.left, self.center, self.right],
            [self.below_left, self.below, self.below_right],
        ]
        return "\n".join("  ".join(f"{fmt(c):<30}" for c in row) for row in rows)


@dataclass
class RangeNeighbourhood:
    """Cells around a range (the frame outside it)."""
    range_coord:   str                              # "C5:F8"
    above_row:     list[CellInfo]                   # cells directly above the range, same cols
    below_row:     list[CellInfo]
    left_col:      list[CellInfo]                   # cells directly left, same rows
    right_col:     list[CellInfo]
    corners:       dict[str, CellInfo | None]    # NW, NE, SW, SE
    inside_summary: dict[str, Any]                  # dtype distribution + density of cells inside


# =============================================================================
# Build merge-resolved grid with rich cell info
# =============================================================================

def _detect_dtype(v: Any) -> str:
    if v is None or v == "": return "blank"
    if isinstance(v, (datetime, date)): return "date"
    if isinstance(v, bool): return "bool"
    if isinstance(v, int): return "int"
    if isinstance(v, float): return "float"
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("="): return "formula"
        return "str"
    return "other"


@tool("build_rich_grid")
def build_rich_grid(sh) -> dict[tuple[int, str], CellInfo]:
    """Walk an openpyxl sheet and return a `{(row, col_letter): CellInfo}` map.

    Merges resolved: every continuation cell is synthesised with the
    anchor's value while the anchor itself carries the merge metadata.
    """
    grid = {}
    # First pass: read direct cell properties for non-merged cells
    for row in sh.iter_rows(values_only=False):
        for cell in row:
            if isinstance(cell, MergedCell):
                continue   # handled below via merge_cells.ranges
            raw_value = cell.value
            fill_color = None
            if cell.fill and cell.fill.fgColor and cell.fill.fgColor.rgb:
                rgb = cell.fill.fgColor.rgb
                if isinstance(rgb, str) and len(rgb) == 8 and rgb != "00000000":
                    fill_color = rgb[2:]   # strip alpha
            is_bold = bool(cell.font and cell.font.bold)
            has_border = bool(cell.border and any(
                bool(getattr(cell.border, s) and getattr(cell.border, s).border_style)
                for s in ("left", "right", "top", "bottom")
            ))
            grid[(cell.row, cell.column_letter)] = CellInfo(
                coord=cell.coordinate,
                row=cell.row,
                col=cell.column_letter,
                value=raw_value,
                raw_value=raw_value,
                dtype=_detect_dtype(raw_value),
                is_merged=False,
                is_merge_anchor=False,
                merge_anchor=None,
                merge_range=None,
                merge_size=None,
                is_bold=is_bold,
                fill_color=fill_color,
                has_border=has_border,
            )
    # Second pass: handle merged ranges
    for mr in sh.merged_cells.ranges:
        top_coord = f"{get_column_letter(mr.min_col)}{mr.min_row}"
        top_value = sh.cell(mr.min_row, mr.min_col).value
        mr_tuple = (mr.min_row, mr.min_col, mr.max_row, mr.max_col)
        mr_size = (mr.max_row - mr.min_row + 1, mr.max_col - mr.min_col + 1)
        for r in range(mr.min_row, mr.max_row + 1):
            for c_i in range(mr.min_col, mr.max_col + 1):
                col_letter = get_column_letter(c_i)
                key = (r, col_letter)
                is_anchor = (r == mr.min_row and c_i == mr.min_col)
                # If anchor, update existing entry
                if is_anchor and key in grid:
                    grid[key].is_merged = True
                    grid[key].is_merge_anchor = True
                    grid[key].merge_anchor = top_coord
                    grid[key].merge_range = mr_tuple
                    grid[key].merge_size = mr_size
                else:
                    # Create a synthetic entry for the merge-continuation cell
                    grid[key] = CellInfo(
                        coord=f"{col_letter}{r}",
                        row=r,
                        col=col_letter,
                        value=top_value,                  # merge-resolved
                        raw_value=None,                   # this cell itself is empty
                        dtype=_detect_dtype(top_value),
                        is_merged=True,
                        is_merge_anchor=False,
                        merge_anchor=top_coord,
                        merge_range=mr_tuple,
                        merge_size=mr_size,
                        is_bold=False,
                        fill_color=None,
                        has_border=False,
                    )
    return grid


# =============================================================================
# Tools
# =============================================================================

@tool("find_around_cell")
def find_around_cell(grid: dict, cell_coord: str) -> CellNeighbourhood:
    """Return the 8 cells around `cell_coord` plus the cell itself."""
    # parse coord like "B4"
    col_letter, row = _split_coord(cell_coord)
    col_idx = column_index_from_string(col_letter)
    center = grid.get((row, col_letter))
    if center is None:
        # Construct an empty centre
        center = CellInfo(coord=cell_coord, row=row, col=col_letter, value=None,
                          raw_value=None, dtype="blank", is_merged=False,
                          is_merge_anchor=False, merge_anchor=None,
                          merge_range=None, merge_size=None,
                          is_bold=False, fill_color=None, has_border=False)
    def at(dr, dc):
        r2 = row + dr
        c2 = get_column_letter(col_idx + dc) if (col_idx + dc) > 0 else None
        if c2 is None or r2 < 1: return None
        return grid.get((r2, c2))
    return CellNeighbourhood(
        center=center,
        above=at(-1, 0),
        below=at(1, 0),
        left=at(0, -1),
        right=at(0, 1),
        above_left=at(-1, -1),
        above_right=at(-1, 1),
        below_left=at(1, -1),
        below_right=at(1, 1),
    )


@tool("find_around_range")
def find_around_range(grid: dict, row_range: tuple[int, int], col_range: tuple[str, str]) -> RangeNeighbourhood:
    """Return the frame around a rectangular range + summary of cells inside."""
    r0, r1 = row_range
    c0_letter, c1_letter = col_range
    c0_idx = column_index_from_string(c0_letter)
    c1_idx = column_index_from_string(c1_letter)

    def at(r, c_i):
        if r < 1 or c_i < 1: return None
        return grid.get((r, get_column_letter(c_i)))

    # cells directly above the range (row r0-1, cols c0..c1)
    above_row = [at(r0 - 1, ci) for ci in range(c0_idx, c1_idx + 1)] if r0 > 1 else []
    # cells directly below
    below_row = [at(r1 + 1, ci) for ci in range(c0_idx, c1_idx + 1)]
    # cells directly left
    left_col = [at(r, c0_idx - 1) for r in range(r0, r1 + 1)] if c0_idx > 1 else []
    # cells directly right
    right_col = [at(r, c1_idx + 1) for r in range(r0, r1 + 1)]
    # corners
    corners = {
        "NW": at(r0 - 1, c0_idx - 1) if (r0 > 1 and c0_idx > 1) else None,
        "NE": at(r0 - 1, c1_idx + 1) if r0 > 1 else None,
        "SW": at(r1 + 1, c0_idx - 1) if c0_idx > 1 else None,
        "SE": at(r1 + 1, c1_idx + 1),
    }
    # inside summary: dtype distribution + density
    inside_cells = [at(r, ci) for r in range(r0, r1 + 1) for ci in range(c0_idx, c1_idx + 1)]
    inside_cells = [c for c in inside_cells if c is not None]
    total = len(inside_cells)
    non_blank = sum(1 for c in inside_cells if c.value not in (None, ""))
    dtype_counts = {}
    for c in inside_cells:
        dtype_counts[c.dtype] = dtype_counts.get(c.dtype, 0) + 1
    inside_summary = {
        "total_cells": total,
        "non_blank":   non_blank,
        "density":     round(non_blank / total, 3) if total else 0.0,
        "dtype_distribution": dtype_counts,
    }
    return RangeNeighbourhood(
        range_coord=f"{c0_letter}{r0}:{c1_letter}{r1}",
        above_row=above_row,
        below_row=below_row,
        left_col=left_col,
        right_col=right_col,
        corners=corners,
        inside_summary=inside_summary,
    )


def _split_coord(coord: str) -> tuple[str, int]:
    """Split 'AB123' → ('AB', 123)."""
    for i, ch in enumerate(coord):
        if ch.isdigit():
            return coord[:i], int(coord[i:])
    return coord, 1

