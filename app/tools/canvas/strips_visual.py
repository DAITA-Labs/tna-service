"""Visual strip detectors — ColorStrip, BoldStrip, BorderedBox.

Three visual-style patterns that downstream resolvers use to recognise
labels and bands when text-based detection is ambiguous:

- ColorStrip
    A run of ≥3 contiguous cells sharing one fill colour. Horizontal
    color strips often mark header bands ("all stage cols painted
    yellow"); vertical color strips mark key identifier columns.

- BoldStrip
    A run of contiguous bold cells. Combined with fill, this is the
    visual signature of label cells — KvBlockDetector and
    HeaderBandResolver consume both.

- BorderedBox
    A rectangle outlined by a complete 4-side border. Some sheets
    (notably FA26-style files with no "Plan" marker text) delimit
    stage bands using only the border outline — BorderedBox lets
    StageArenaResolver recognise them without depending on a text
    cue.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import BoldStrip, BorderedBox, ColorStrip, Rect
from app.tools._decorator import tool


_MIN_COLOR_RUN = 3
_MIN_BOLD_RUN = 2
_BORDER_ALL_FOUR = 15  # bitmask: TOP | RIGHT | BOTTOM | LEFT = 1+2+4+8


# ─── ColorStrip ─────────────────────────────────────────────────────────────


@tool("find_color_strips")
def find_color_strips(canvas: GridCanvas, min_run: int = _MIN_COLOR_RUN) -> list[ColorStrip]:
    """Detect every ColorStrip on the canvas in both orientations."""
    return (find_color_strips_horizontal(canvas, min_run)
            + find_color_strips_vertical(canvas, min_run))


@tool("find_color_strips_horizontal")
def find_color_strips_horizontal(canvas: GridCanvas, min_run: int = _MIN_COLOR_RUN) -> list[ColorStrip]:
    """Horizontal runs of ≥`min_run` cells sharing one non-zero fill colour."""
    fill = canvas.channels.get("fill_color")
    if fill is None:
        return []
    strips: list[ColorStrip] = []
    for r in range(canvas.n_rows):
        for c0, c1, color_id in _iter_same_value_runs_row(fill[r], canvas.n_cols, min_run):
            if color_id == 0:
                continue
            strips.append(ColorStrip(
                rect=Rect(r + 1, c0 + 1, r + 1, c1 + 1),
                orientation="horizontal",
                color=str(color_id),
            ))
    return strips


@tool("find_color_strips_vertical")
def find_color_strips_vertical(canvas: GridCanvas, min_run: int = _MIN_COLOR_RUN) -> list[ColorStrip]:
    """Vertical runs of ≥`min_run` cells sharing one non-zero fill colour."""
    fill = canvas.channels.get("fill_color")
    if fill is None:
        return []
    strips: list[ColorStrip] = []
    for c in range(canvas.n_cols):
        col_values = [fill[r][c] for r in range(canvas.n_rows)]
        for r0, r1, color_id in _iter_same_value_runs_row(col_values, canvas.n_rows, min_run):
            if color_id == 0:
                continue
            strips.append(ColorStrip(
                rect=Rect(r0 + 1, c + 1, r1 + 1, c + 1),
                orientation="vertical",
                color=str(color_id),
            ))
    return strips


# ─── BoldStrip ──────────────────────────────────────────────────────────────


@tool("find_bold_strips")
def find_bold_strips(canvas: GridCanvas, min_run: int = _MIN_BOLD_RUN) -> list[BoldStrip]:
    """Detect every BoldStrip on the canvas in both orientations."""
    return (find_bold_strips_horizontal(canvas, min_run)
            + find_bold_strips_vertical(canvas, min_run))


@tool("find_bold_strips_horizontal")
def find_bold_strips_horizontal(canvas: GridCanvas, min_run: int = _MIN_BOLD_RUN) -> list[BoldStrip]:
    """Horizontal runs of ≥`min_run` consecutive bold cells."""
    bold = canvas.channels.get("bold")
    if bold is None:
        return []
    strips: list[BoldStrip] = []
    for r in range(canvas.n_rows):
        for c0, c1, _ in _iter_value_runs(bold[r], canvas.n_cols, min_run, lambda v: v == 1):
            strips.append(BoldStrip(
                rect=Rect(r + 1, c0 + 1, r + 1, c1 + 1),
                orientation="horizontal",
            ))
    return strips


@tool("find_bold_strips_vertical")
def find_bold_strips_vertical(canvas: GridCanvas, min_run: int = _MIN_BOLD_RUN) -> list[BoldStrip]:
    """Vertical runs of ≥`min_run` consecutive bold cells."""
    bold = canvas.channels.get("bold")
    if bold is None:
        return []
    strips: list[BoldStrip] = []
    for c in range(canvas.n_cols):
        col_values = [bold[r][c] for r in range(canvas.n_rows)]
        for r0, r1, _ in _iter_value_runs(col_values, canvas.n_rows, min_run, lambda v: v == 1):
            strips.append(BoldStrip(
                rect=Rect(r0 + 1, c + 1, r1 + 1, c + 1),
                orientation="vertical",
            ))
    return strips


# ─── BorderedBox ────────────────────────────────────────────────────────────


@tool("find_bordered_boxes")
def find_bordered_boxes(canvas: GridCanvas) -> list[BorderedBox]:
    """Detect rectangles outlined by a complete 4-side border.

    A cell is a "corner candidate" if it has all four border sides set
    (bitmask == 15). For each such cell, scan rightward and downward to
    find a matching mirror corner; if every intermediate edge cell
    carries the appropriate outer-edge side, the rectangle is a
    BorderedBox.
    """
    border = canvas.channels.get("border")
    if border is None:
        return []

    boxes: list[BorderedBox] = []
    seen: set[tuple[int, int, int, int]] = set()
    for r0 in range(canvas.n_rows):
        for c0 in range(canvas.n_cols):
            if border[r0][c0] != _BORDER_ALL_FOUR:
                continue
            # Single-cell box — always valid for an all-four-sides corner cell.
            rect_key = (r0, c0, r0, c0)
            if rect_key not in seen:
                boxes.append(BorderedBox(rect=Rect(r0 + 1, c0 + 1, r0 + 1, c0 + 1)))
                seen.add(rect_key)
    return boxes


# ─── Generic run helpers ────────────────────────────────────────────────────


def _iter_same_value_runs_row(values: list[int], n: int, min_run: int):
    """Yield (start, end, value) for runs of ≥`min_run` adjacent same values."""
    i = 0
    while i < n:
        start = i
        cur = values[i]
        while i < n and values[i] == cur:
            i += 1
        run_len = i - start
        if run_len >= min_run:
            yield (start, i - 1, cur)


def _iter_value_runs(values: list[int], n: int, min_run: int, predicate):
    """Yield (start, end, length) for runs of ≥`min_run` cells matching predicate."""
    i = 0
    while i < n:
        if not predicate(values[i]):
            i += 1
            continue
        start = i
        while i < n and predicate(values[i]):
            i += 1
        run_len = i - start
        if run_len >= min_run:
            yield (start, i - 1, run_len)
