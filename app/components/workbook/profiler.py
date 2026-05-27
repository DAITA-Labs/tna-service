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

from haystack import component

from app.artifacts.workbook import (
    SIGNATURE_LABEL_ROWS,
    SIGNATURE_SAMPLE_ROWS,
    DtypeHistogram,
    LabelPosition,
    SheetSignature,
)
from app.components._base import Component


# dtype slot identifiers — internal to the row-walk loop. The named
# `DtypeHistogram` carries the semantic shape; these constants only key
# into the local counts list.
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
    dtype_rows: list[DtypeHistogram] = []
    labels: set[LabelPosition] = set()

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
                    labels.add(LabelPosition(row=r, col=c, text=normalised))
        dtype_rows.append(DtypeHistogram(
            n_blank=counts[_BLANK], n_str=counts[_STR], n_int=counts[_INT],
            n_float=counts[_FLOAT], n_date=counts[_DATE],
        ))

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


@component
class WorkbookProfiler(Component):
    """Haystack wrapper around `compute_sheet_signature`.

    Inputs:
        workbook — an openpyxl Workbook

    Outputs:
        signatures — list[SheetSignature], one per worksheet in workbook order
    """

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(signatures=list[SheetSignature])
    def run(self, workbook) -> dict:
        signatures = [compute_sheet_signature(ws) for ws in workbook.worksheets]
        return {"signatures": signatures}
