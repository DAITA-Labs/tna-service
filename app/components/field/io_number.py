"""IoNumberExtractor — emits Finding(canonical="io_number") per PLI.

The IO number is a per-PLI identifier (also called job no, internal
order, PO no depending on the spreadsheet author). The extractor reads
candidate columns + data rows from the bundle's LayoutHint, walks the
chosen column row-by-row, and coerces each raw cell value into a
string (IO codes are identifiers, never numerics).
"""
from __future__ import annotations

from typing import Any

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component


_CANONICAL = "io_number"


@component
class IoNumberExtractor(Component):
    """Extract `io_number` Findings from a ClusterAnchorBundle.

    Supports ROW_PER_PLI (vertical PLI axis). Other axes return [] —
    other extractors / future work will cover sectional / sheet / horizontal.
    """

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(findings=list[Finding])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        if bundle.hint.axes.pli_axis != "vertical":
            return {"findings": []}

        columns = bundle.hint.candidate_columns.get(_CANONICAL, [])
        rows = bundle.hint.candidate_rows.get(_CANONICAL, [])
        if not columns or not rows:
            return {"findings": []}

        col_idx = columns[0]  # multi-column arbitration deferred to a later validator
        col_letter = get_column_letter(col_idx)
        band = bundle.hint.header_band
        label_coord = (col_letter, band.rect.r0 if band else 1)

        findings: list[Finding] = []
        for row in rows:
            raw = bundle.canvas.cell_values[row - 1][col_idx - 1]
            if raw is None or raw == "":
                continue
            findings.append(Finding(
                canonical=_CANONICAL,
                label_coord=label_coord,
                value_coord=(col_letter, row),
                value=_coerce_io_code(raw),
                confidence=Confidence.MEDIUM,
                evidence=["HEADER_BAND_MEMBER", "DTYPE_MATCH"],
            ))
        return {"findings": findings}


def _coerce_io_code(value: Any) -> str:
    """Normalise raw cell value into an IO-code string.

    openpyxl may type a numeric IO code as int or float; whole-number floats
    (1063.0) drop the trailing zero. Strings are whitespace-stripped.
    """
    if isinstance(value, bool):  # bool is a subclass of int — handle first
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value).strip()
