"""Profiler — compute a `SheetSignature` from a raw openpyxl worksheet.

`compute_sheet_signature` is intentionally lighter than `build_canvas`:
the profiler runs once per sheet during the routing pre-pass, while the
full canvas is only ever built for sheets that survive role
classification. The profiler therefore reads cell values + types
directly from openpyxl without populating channels, computing borders,
or resolving merges.

The signature samples only the first `SIGNATURE_SAMPLE_ROWS` rows
(structural pattern lives in the header region). Sheets shorter than
that simply yield a smaller fingerprint.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

from app.artifacts.workbook import (
    SIGNATURE_LABEL_ROWS,
    SIGNATURE_SAMPLE_ROWS,
    SheetSignature,
)


# dtype slot order — must match SheetSignature.dtype_per_row's tuple shape
# (n_blank, n_str, n_int, n_float, n_date).
_BLANK = 0
_STR = 1
_INT = 2
_FLOAT = 3
_DATE = 4

# Strings parseable as a date (heuristic — same intent as build.py but
# kept local to avoid pulling in the full canvas dependency chain).
_DATE_PAT = re.compile(r"^\d{1,4}[-/.]\d{1,2}([-/.]\d{1,4})?$")

# Strip whitespace + collapse internal runs when normalising label text.
_WS = re.compile(r"\s+")


def compute_sheet_signature(sheet) -> SheetSignature:
    """Walk the first `SIGNATURE_SAMPLE_ROWS` rows and emit a SheetSignature."""
    n_rows = sheet.max_row or 0
    n_cols = sheet.max_column or 0

    sample_row_end = min(n_rows, SIGNATURE_SAMPLE_ROWS)
    label_row_end = min(n_rows, SIGNATURE_LABEL_ROWS)

    mask: set[tuple[int, int]] = set()
    dtype_rows: list[tuple[int, int, int, int, int]] = []
    labels: set[tuple[int, int, str]] = set()

    for r in range(1, sample_row_end + 1):
        counts = [0, 0, 0, 0, 0]
        for c in range(1, n_cols + 1):
            value = sheet.cell(row=r, column=c).value
            slot = _classify(value)
            counts[slot] += 1
            if slot != _BLANK:
                mask.add((r, c))
            if r <= label_row_end and slot == _STR:
                normalised = _normalise(value)
                if normalised:
                    labels.add((r, c, normalised))
        dtype_rows.append((counts[_BLANK], counts[_STR], counts[_INT],
                            counts[_FLOAT], counts[_DATE]))

    return SheetSignature(
        sheet_name=sheet.title,
        n_rows=n_rows,
        n_cols=n_cols,
        non_blank_mask=frozenset(mask),
        dtype_per_row=tuple(dtype_rows),
        label_positions=frozenset(labels),
    )


def _classify(value: Any) -> int:
    """Return the dtype slot for a single cell value."""
    if value is None or value == "":
        return _BLANK
    if isinstance(value, bool):  # bool is subclass of int — check first
        return _INT
    if isinstance(value, dt.datetime) or isinstance(value, dt.date):
        return _DATE
    if isinstance(value, int):
        return _INT
    if isinstance(value, float):
        return _FLOAT
    if isinstance(value, str):
        if _DATE_PAT.match(value.strip()):
            return _DATE
        return _STR
    return _STR


def _normalise(text: str) -> str:
    """Lowercase + collapse whitespace so similarity is robust to formatting."""
    return _WS.sub(" ", text.strip().lower())
