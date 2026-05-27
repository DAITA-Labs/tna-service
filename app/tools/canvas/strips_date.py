"""DateStrip detector — runs of contiguous date cells.

Emits one `DateStrip` per run of ≥3 consecutive date cells in a line.
Runs are detected in both orientations: vertical (column-wise) and
horizontal (row-wise). Each strip carries its bounding rect, orientation,
and density (fraction of cells in the rect that are dates).

Consumed by:
  - StageArenaResolver — vertical DateStrips with plan markers nearby
                          define stage arenas in ROW_PER_PLI / SECTION layouts.
  - SHEET_IS_PLI horizontal stages — horizontal DateStrips identify the
                                      plan_date row inside a band.
  - date-identifier extraction — k:v / column claim is anchored on a
                                  DateStrip candidate column / row.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import DateStrip, Rect
from app.tools._decorator import tool


# A DateStrip needs at least this many contiguous date cells to register.
_MIN_RUN = 3


@tool("find_date_strips")
def find_date_strips(canvas: GridCanvas, min_run: int = _MIN_RUN) -> list[DateStrip]:
    """Return every DateStrip on the canvas in both orientations."""
    return find_date_strips_vertical(canvas, min_run) + find_date_strips_horizontal(canvas, min_run)


@tool("find_date_strips_vertical")
def find_date_strips_vertical(canvas: GridCanvas, min_run: int = _MIN_RUN) -> list[DateStrip]:
    """Detect vertical (column-wise) runs of ≥`min_run` date cells."""
    strips: list[DateStrip] = []
    dtype = canvas.channels.get("dtype")
    if dtype is None:
        return strips

    for c in range(canvas.n_cols):
        for r0, r1, run_len in _iter_runs_column(dtype, c, canvas.n_rows, _is_date):
            if run_len < min_run:
                continue
            strips.append(DateStrip(
                rect=Rect(r0 + 1, c + 1, r1 + 1, c + 1),
                orientation="vertical",
                density=1.0,
            ))
    return strips


@tool("find_date_strips_horizontal")
def find_date_strips_horizontal(canvas: GridCanvas, min_run: int = _MIN_RUN) -> list[DateStrip]:
    """Detect horizontal (row-wise) runs of ≥`min_run` date cells."""
    strips: list[DateStrip] = []
    dtype = canvas.channels.get("dtype")
    if dtype is None:
        return strips

    for r in range(canvas.n_rows):
        for c0, c1, run_len in _iter_runs_row(dtype, r, canvas.n_cols, _is_date):
            if run_len < min_run:
                continue
            strips.append(DateStrip(
                rect=Rect(r + 1, c0 + 1, r + 1, c1 + 1),
                orientation="horizontal",
                density=1.0,
            ))
    return strips


# ─── Generic run helpers (reusable across strip detectors) ──────────────────


def _is_date(dtype_value: int) -> bool:
    """Predicate: the dtype channel value 1 marks a date cell (per app.tools.canvas.build)."""
    return dtype_value == 1


def _iter_runs_column(channel: list[list[int]], col: int, n_rows: int, predicate) -> list[tuple[int, int, int]]:
    """Yield (r_start, r_end, length) tuples for runs of cells in `col` matching predicate."""
    runs: list[tuple[int, int, int]] = []
    r = 0
    while r < n_rows:
        if not predicate(channel[r][col]):
            r += 1
            continue
        start = r
        while r < n_rows and predicate(channel[r][col]):
            r += 1
        runs.append((start, r - 1, r - start))
    return runs


def _iter_runs_row(channel: list[list[int]], row: int, n_cols: int, predicate) -> list[tuple[int, int, int]]:
    """Yield (c_start, c_end, length) tuples for runs of cells in `row` matching predicate."""
    runs: list[tuple[int, int, int]] = []
    c = 0
    while c < n_cols:
        if not predicate(channel[row][c]):
            c += 1
            continue
        start = c
        while c < n_cols and predicate(channel[row][c]):
            c += 1
        runs.append((start, c - 1, c - start))
    return runs
