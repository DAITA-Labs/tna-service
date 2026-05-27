"""QuantityExtractor — emits Finding(canonical="quantity") per PLI.

Quantity is a per-PLI numeric — the order count in pieces (or sometimes
units). Raw values may arrive as:

  - int (1200)
  - float (1200.0 from openpyxl's tendency to type integer cells as float;
           or genuinely fractional values like 1200.5)
  - string ("1200", "1,200", "1200 pcs", " 1200  ")

The coercer normalises to int when the value is whole (counting pieces),
falls back to float for genuinely fractional values, and returns the
raw string when nothing parses. Blank and zero cells are skipped — a
PLI with zero quantity is not a usable order line.
"""
from __future__ import annotations

import re
from typing import Any

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component


_CANONICAL = "quantity"

# Strip thousands separators (commas, spaces) and trailing unit text like "pcs"
# before attempting numeric parse.
_DIGITS_AND_DOT = re.compile(r"^-?\d+(\.\d+)?$")


@component
class QuantityExtractor(Component):
    """Extract `quantity` Findings from a ClusterAnchorBundle (vertical PLI axis)."""

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

        col_idx = columns[0]
        col_letter = get_column_letter(col_idx)
        band = bundle.hint.header_band
        label_coord = (col_letter, band.rect.r0 if band else 1)

        findings: list[Finding] = []
        for row in rows:
            raw = bundle.canvas.cell_values[row - 1][col_idx - 1]
            value = _coerce_quantity(raw)
            if value is None or value == 0:
                continue
            findings.append(Finding(
                canonical=_CANONICAL,
                label_coord=label_coord,
                value_coord=(col_letter, row),
                value=value,
                confidence=Confidence.MEDIUM,
                evidence=["HEADER_BAND_MEMBER", "DTYPE_MATCH"],
            ))
        return {"findings": findings}


def _coerce_quantity(value: Any) -> int | float | str | None:
    """Normalise a raw cell value into a quantity number; return None on blank."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):  # bool is subclass of int — reject defensively
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, str):
        # Strip thousands separators + trailing unit text.
        cleaned = value.replace(",", "").replace(" ", "").strip().lower()
        # Trim any unit suffix ("pcs", "units", "pc", "ea") at the end.
        for unit in ("pcs", "units", "unit", "pc", "ea"):
            if cleaned.endswith(unit):
                cleaned = cleaned[: -len(unit)]
                break
        if not cleaned:
            return None
        if _DIGITS_AND_DOT.match(cleaned):
            num = float(cleaned)
            return int(num) if num.is_integer() else num
        return value  # unparseable — preserve raw so validators can flag it
    return None
