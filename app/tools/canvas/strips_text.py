"""SameLengthStrip + LongTextStrip detectors — string-column shape signals.

Two text-column patterns useful for identifier reinforcement:

- SameLengthStrip
    >70% of a column's string cells share one character length.
    A strong reinforcing signal for io_number / style_code / color_code
    columns where supplier IDs are typically fixed-length within a sheet
    (e.g. all style codes are 6 digits).

- LongTextStrip
    String cells in the column average ≥20 characters.
    Reinforces fabric_code (composite descriptive strings like
    "2X2 RIB/100% COTTON/34S////18GG/260") and style_name / metadata
    description columns.

Both detectors are vertical-only — the canonical use is per-PLI
identifier columns under a tabular header band.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import LongTextStrip, Rect, SameLengthStrip
from app.tools._decorator import tool


_DTYPE_STR = 4
_DTYPE_BLANK = 0

_SAME_LENGTH_MIN_DENSITY = 0.70
_LONG_TEXT_MIN_MEAN = 20.0
_MIN_NON_BLANK_STRINGS = 3


@tool("find_same_length_strips")
def find_same_length_strips(canvas: GridCanvas,
                             min_density: float = _SAME_LENGTH_MIN_DENSITY,
                             min_non_blank: int = _MIN_NON_BLANK_STRINGS) -> list[SameLengthStrip]:
    """Detect vertical columns where >70% of string cells share one char length."""
    strips: list[SameLengthStrip] = []
    dtype = canvas.channels.get("dtype")
    if dtype is None:
        return strips

    for c in range(canvas.n_cols):
        r_start, r_end, length_counts = _collect_string_lengths(canvas, c)
        if r_start is None:
            continue
        total = sum(length_counts.values())
        if total < min_non_blank:
            continue
        dominant_length, dominant_count = max(length_counts.items(), key=lambda kv: kv[1])
        density = dominant_count / total
        if density < min_density:
            continue
        strips.append(SameLengthStrip(
            rect=Rect(r_start + 1, c + 1, r_end + 1, c + 1),
            length=dominant_length,
            density=density,
        ))
    return strips


@tool("find_long_text_strips")
def find_long_text_strips(canvas: GridCanvas,
                           min_mean: float = _LONG_TEXT_MIN_MEAN,
                           min_non_blank: int = _MIN_NON_BLANK_STRINGS) -> list[LongTextStrip]:
    """Detect vertical columns whose string cells average ≥`min_mean` characters."""
    strips: list[LongTextStrip] = []
    dtype = canvas.channels.get("dtype")
    if dtype is None:
        return strips

    for c in range(canvas.n_cols):
        r_start, r_end, lengths = _collect_string_length_list(canvas, c)
        if r_start is None or len(lengths) < min_non_blank:
            continue
        mean = sum(lengths) / len(lengths)
        if mean < min_mean:
            continue
        strips.append(LongTextStrip(
            rect=Rect(r_start + 1, c + 1, r_end + 1, c + 1),
            mean_length=mean,
        ))
    return strips


# ─── Per-column collectors ──────────────────────────────────────────────────


def _collect_string_lengths(canvas: GridCanvas, col: int) -> tuple[int | None, int | None, dict[int, int]]:
    """Return (r_start, r_end, {char_length: count}) over string cells in `col`."""
    dtype = canvas.channels["dtype"]
    r_start: int | None = None
    r_end: int | None = None
    counts: dict[int, int] = {}

    for r in range(canvas.n_rows):
        if dtype[r][col] != _DTYPE_STR:
            continue
        value = canvas.cell_values[r][col]
        if not isinstance(value, str):
            continue
        if r_start is None:
            r_start = r
        r_end = r
        text_len = len(value.strip())
        if text_len == 0:
            continue
        counts[text_len] = counts.get(text_len, 0) + 1
    return r_start, r_end, counts


def _collect_string_length_list(canvas: GridCanvas, col: int) -> tuple[int | None, int | None, list[int]]:
    """Return (r_start, r_end, [char_lengths]) over string cells in `col`."""
    dtype = canvas.channels["dtype"]
    r_start: int | None = None
    r_end: int | None = None
    lengths: list[int] = []

    for r in range(canvas.n_rows):
        if dtype[r][col] != _DTYPE_STR:
            continue
        value = canvas.cell_values[r][col]
        if not isinstance(value, str):
            continue
        if r_start is None:
            r_start = r
        r_end = r
        text_len = len(value.strip())
        if text_len > 0:
            lengths.append(text_len)
    return r_start, r_end, lengths
