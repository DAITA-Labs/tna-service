"""Merge-pattern detectors — MergeSpan, NonMergedStrip, MergedColumnStrip.

Three views over the canvas's merge_ranges:

- MergeSpan
    One record per merge range, tagged with orientation ("horizontal" /
    "vertical" / "block"). Horizontal spans in header rows carry the
    sibling-resolution signal (FABRIC merged across 5 cols → 1st col
    is fabric_code, 2nd is fabric_name).

- NonMergedStrip
    A column whose data-row cells have zero merge participation. A
    strong reinforcing signal for quantity, date trio, and stage
    planned_date columns — these are typically unique per PLI and
    therefore never merged.

- MergedColumnStrip
    A column whose data-row cells contain multiple vertical merges.
    Signals an identifier column where one PO covers multiple variants
    (CHRISTIAN BERG, fabric_code spanning color rows). Used by
    IdentifierComponent's cardinality validator to expand a single
    finding into N PLI-row coverage.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import (
    MergeSpan,
    MergedColumnStrip,
    NonMergedStrip,
    Rect,
)
from app.tools._decorator import tool


_MIN_MERGES_FOR_COLUMN_STRIP = 2


# ─── MergeSpan ──────────────────────────────────────────────────────────────


@tool("find_merge_spans")
def find_merge_spans(canvas: GridCanvas) -> list[MergeSpan]:
    """Yield one MergeSpan per merge range, orientation-tagged."""
    return [
        MergeSpan(rect=Rect(r0, c0, r1, c1), orientation=_classify_orientation(r0, c0, r1, c1))
        for (r0, c0, r1, c1) in canvas.merge_ranges
    ]


def _classify_orientation(r0: int, c0: int, r1: int, c1: int) -> str:
    """Return 'horizontal' for 1×N, 'vertical' for N×1, 'block' for M×N (M,N ≥ 2)."""
    n_rows = r1 - r0 + 1
    n_cols = c1 - c0 + 1
    if n_rows == 1 and n_cols >= 2:
        return "horizontal"
    if n_cols == 1 and n_rows >= 2:
        return "vertical"
    return "block"


# ─── NonMergedStrip ─────────────────────────────────────────────────────────


@tool("find_non_merged_strips_vertical")
def find_non_merged_strips_vertical(canvas: GridCanvas) -> list[NonMergedStrip]:
    """For each column, emit a NonMergedStrip if no merge range covers it."""
    cols_with_merges = _columns_touched_by_merges(canvas)
    strips: list[NonMergedStrip] = []
    for c in range(canvas.n_cols):
        if (c + 1) in cols_with_merges:
            continue
        strips.append(NonMergedStrip(
            rect=Rect(1, c + 1, canvas.n_rows, c + 1),
            orientation="vertical",
        ))
    return strips


@tool("find_non_merged_strips_horizontal")
def find_non_merged_strips_horizontal(canvas: GridCanvas) -> list[NonMergedStrip]:
    """For each row, emit a NonMergedStrip if no merge range covers it."""
    rows_with_merges = _rows_touched_by_merges(canvas)
    strips: list[NonMergedStrip] = []
    for r in range(canvas.n_rows):
        if (r + 1) in rows_with_merges:
            continue
        strips.append(NonMergedStrip(
            rect=Rect(r + 1, 1, r + 1, canvas.n_cols),
            orientation="horizontal",
        ))
    return strips


# ─── MergedColumnStrip ──────────────────────────────────────────────────────


@tool("find_merged_column_strips")
def find_merged_column_strips(canvas: GridCanvas,
                                min_merges: int = _MIN_MERGES_FOR_COLUMN_STRIP) -> list[MergedColumnStrip]:
    """Emit a MergedColumnStrip per column carrying ≥`min_merges` vertical merges."""
    vert_merges_by_col: dict[int, int] = {}
    for (r0, c0, r1, c1) in canvas.merge_ranges:
        if c0 != c1 or r1 == r0:
            continue   # not a vertical-only merge
        vert_merges_by_col[c0] = vert_merges_by_col.get(c0, 0) + 1

    strips: list[MergedColumnStrip] = []
    for col, count in vert_merges_by_col.items():
        if count < min_merges:
            continue
        strips.append(MergedColumnStrip(
            rect=Rect(1, col, canvas.n_rows, col),
            merge_count=count,
        ))
    return strips


# ─── Helpers ────────────────────────────────────────────────────────────────


def _columns_touched_by_merges(canvas: GridCanvas) -> set[int]:
    """Return the set of 1-indexed columns that any merge range covers."""
    touched: set[int] = set()
    for (r0, c0, r1, c1) in canvas.merge_ranges:
        for col in range(c0, c1 + 1):
            touched.add(col)
    return touched


def _rows_touched_by_merges(canvas: GridCanvas) -> set[int]:
    """Return the set of 1-indexed rows that any merge range covers."""
    touched: set[int] = set()
    for (r0, c0, r1, c1) in canvas.merge_ranges:
        for row in range(r0, r1 + 1):
            touched.add(row)
    return touched
