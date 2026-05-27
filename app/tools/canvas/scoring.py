"""Column-finalization scoring for field extractors.

`score_column_for_canonical` combines three orthogonal signals into a
single [0, 1] confidence score that an extractor uses to pick among
candidate columns produced by the LayoutHint. The hint's header-band
rank is necessary (the column matched some spec alias) but not
sufficient — the data rows themselves have to look right.

Signals (each in [0, 1]):

  strip_overlap     — 1.0 if any strip in `strips` overlaps the column
                       and at least one data row, else 0.0. The strip
                       was emitted by the structure phase, so this signal
                       captures "the column already passed a dtype-density
                       check at structure-phase time".

  dtype_match_rate  — fraction of non-blank cells in `(col_idx × rows)`
                       whose canvas `dtype` channel matches the spec's
                       `value_dtype`. Computed cell-by-cell so we see
                       the actual per-cell dtype distribution.

  constraint_pass   — fraction of non-blank cells whose value passes
                       `spec.value_constraints`. Optional: when the spec
                       has no constraints set this defaults to 1.0.

Combined score:  0.4 * strip_overlap + 0.4 * dtype_match_rate + 0.2 * constraint_pass

The constraint signal is intentionally light-weight (just min/max/len
checks). Heavier value validation belongs in dedicated validator
components later in the pipeline.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from app.artifacts.canvas import GridCanvas
from app.specs._base import FieldSpec
from app.specs.enums import ValueDtype
from app.tools._decorator import tool


# Mirror app.tools.canvas.build's dtype channel codes so we can interpret
# the canvas's `dtype` channel without importing from build (avoiding a
# circular import path).
_DTYPE_BLANK, _DTYPE_DATE, _DTYPE_INT, _DTYPE_FLOAT, _DTYPE_STR = 0, 1, 2, 3, 4


_STRIP_WEIGHT = 0.4
_DTYPE_WEIGHT = 0.4
_CONSTRAINT_WEIGHT = 0.2


@tool("score_column_for_canonical")
def score_column_for_canonical(canvas: GridCanvas,
                                  col_idx: int,
                                  rows: list[int],
                                  spec: FieldSpec,
                                  strips: list) -> float:
    """Return a [0, 1] score for how confidently `col_idx` carries `spec.canonical`.

    Combines strip overlap + per-cell dtype match + per-cell constraint
    pass rate. See module docstring for the weighting.
    """
    if not rows:
        return 0.0

    strip_score = 1.0 if _column_overlaps_any_strip(strips, col_idx, rows) else 0.0
    dtype_score = _dtype_match_rate(canvas, col_idx, rows, spec.value_dtype)
    constraint_score = _constraint_pass_rate(canvas, col_idx, rows, spec)

    return (
        _STRIP_WEIGHT * strip_score
        + _DTYPE_WEIGHT * dtype_score
        + _CONSTRAINT_WEIGHT * constraint_score
    )


def _column_overlaps_any_strip(strips: list, col_idx: int, rows: list[int]) -> bool:
    """True when any strip's rect overlaps col_idx and at least one data row."""
    row_set = set(rows)
    for strip in strips:
        rect = strip.rect
        if rect.c0 <= col_idx <= rect.c1 and any(
            r in row_set for r in range(rect.r0, rect.r1 + 1)
        ):
            return True
    return False


def _dtype_match_rate(canvas: GridCanvas,
                        col_idx: int,
                        rows: list[int],
                        expected: ValueDtype) -> float:
    """Fraction of non-blank cells whose canvas dtype code matches `expected`."""
    if expected == ValueDtype.ANY:
        return 1.0  # spec accepts anything; can't disqualify on dtype

    dtype_channel = canvas.channels.get("dtype")
    if dtype_channel is None:
        return 0.0

    expected_codes = _EXPECTED_DTYPE_CODES[expected]
    matching = 0
    non_blank = 0
    for r in rows:
        code = dtype_channel[r - 1][col_idx - 1]
        if code == _DTYPE_BLANK:
            continue
        non_blank += 1
        if code in expected_codes:
            matching += 1
    return matching / non_blank if non_blank else 0.0


def _constraint_pass_rate(canvas: GridCanvas,
                            col_idx: int,
                            rows: list[int],
                            spec: FieldSpec) -> float:
    """Fraction of non-blank cells whose value passes `spec.value_constraints`.

    Returns 1.0 when the spec carries no constraints (vacuously satisfied).
    """
    constraints = spec.value_constraints
    if (constraints.min is None and constraints.max is None
            and constraints.min_len is None and constraints.max_len is None):
        return 1.0

    passing = 0
    non_blank = 0
    for r in rows:
        value = canvas.cell_values[r - 1][col_idx - 1]
        if value is None or value == "":
            continue
        non_blank += 1
        if _value_passes_constraints(value, constraints):
            passing += 1
    return passing / non_blank if non_blank else 0.0


def _value_passes_constraints(value: Any, constraints) -> bool:
    """Check a single value against min/max (numeric) + min_len/max_len (string)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if constraints.min is not None and value < constraints.min:
            return False
        if constraints.max is not None and value > constraints.max:
            return False
    if isinstance(value, str):
        length = len(value.strip())
        if constraints.min_len is not None and length < constraints.min_len:
            return False
        if constraints.max_len is not None and length > constraints.max_len:
            return False
    return True


# ValueDtype → set of canvas dtype-channel codes that count as matching.
_EXPECTED_DTYPE_CODES: dict[ValueDtype, set[int]] = {
    ValueDtype.INT:  {_DTYPE_INT, _DTYPE_FLOAT},   # ints stored as floats also count
    ValueDtype.DATE: {_DTYPE_DATE},
    ValueDtype.STR:  {_DTYPE_STR},
    ValueDtype.ANY:  {_DTYPE_BLANK, _DTYPE_DATE, _DTYPE_INT, _DTYPE_FLOAT, _DTYPE_STR},
}
