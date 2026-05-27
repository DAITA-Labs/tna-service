"""QuantityExtractor — spec-driven per-PLI numeric extraction.

Three signals combine to produce each Finding:

  1. **Header match** — the column appears in `hint.candidate_columns["quantity"]`
     (its header cell matched a quantity-spec alias). Required to participate.

  2. **IntStrip confirmation** — the column also appears in `bag.int_strips`
     covering the PLI data rows. The structure phase already classified
     this column as ≥80% int; that's the strongest possible confirmation.

  3. **`QUANTITY_SPEC.value_constraints`** — each cell value is checked
     against `min=1, max=100000`. A violation lowers confidence and tags
     the finding with `CONSTRAINT:<which>`.

Confidence ladder per cell:

  HIGH    header_band + int_strip + constraints satisfied
  MEDIUM  header_band + constraints satisfied, no int_strip
  LOW     header_band but a constraint was violated (extreme outlier,
          non-numeric garbage that survived coercion)
"""
from __future__ import annotations

import re
from typing import Any

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.structure import StructureBag
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.specs import QUANTITY_SPEC


# Strip thousands separators (commas, spaces) and trailing unit text before
# attempting numeric parse.
_DIGITS_AND_DOT = re.compile(r"^-?\d+(\.\d+)?$")


@component
class QuantityExtractor(Component):
    """Extract `quantity` Findings using spec constraints + bag.int_strips."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(findings=list[Finding])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        if bundle.hint.axes.pli_axis != "vertical":
            return {"findings": []}

        canonical = QUANTITY_SPEC.canonical
        columns = bundle.hint.candidate_columns.get(canonical, [])
        rows = bundle.hint.candidate_rows.get(canonical, [])
        if not columns or not rows:
            return {"findings": []}

        col_idx = columns[0]
        col_letter = get_column_letter(col_idx)
        band = bundle.hint.header_band
        label_coord = (col_letter, band.rect.r0 if band else 1)

        int_strip_confirmed = _column_has_int_strip(bundle.bag, col_idx, rows)
        constraints = QUANTITY_SPEC.value_constraints

        findings: list[Finding] = []
        for row in rows:
            raw = bundle.canvas.cell_values[row - 1][col_idx - 1]
            value = _coerce_quantity(raw)
            if value is None or value == 0:
                continue

            evidence: list[str] = ["HEADER_BAND_MEMBER"]
            if int_strip_confirmed:
                evidence.append("INT_STRIP_CONFIRMED")

            breach = _check_constraints(value, constraints)
            if breach is not None:
                evidence.append(f"CONSTRAINT:{breach}")
                confidence = Confidence.LOW
            elif int_strip_confirmed:
                confidence = Confidence.HIGH
            else:
                confidence = Confidence.MEDIUM

            findings.append(Finding(
                canonical=canonical,
                label_coord=label_coord,
                value_coord=(col_letter, row),
                value=value,
                confidence=confidence,
                evidence=evidence,
            ))
        return {"findings": findings}


def _column_has_int_strip(bag: StructureBag, col_idx: int, rows: list[int]) -> bool:
    """True when an IntStrip overlaps `col_idx` and at least one of `rows`."""
    row_set = set(rows)
    for strip in bag.int_strips:
        rect = strip.rect
        if rect.c0 <= col_idx <= rect.c1 and any(
            r in row_set for r in range(rect.r0, rect.r1 + 1)
        ):
            return True
    return False


def _check_constraints(value: Any, constraints) -> str | None:
    """Return a short constraint-name token if violated, else None."""
    if isinstance(value, str):
        return "value_not_numeric"  # garbage that survived coercion
    if constraints.min is not None and value < constraints.min:
        return "below_min"
    if constraints.max is not None and value > constraints.max:
        return "above_max"
    return None


def _coerce_quantity(value: Any) -> int | float | str | None:
    """Normalise raw cell value to a number, or None when blank."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None  # bool is subclass of int — reject defensively
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace(" ", "").strip().lower()
        for unit in ("pcs", "units", "unit", "pc", "ea"):
            if cleaned.endswith(unit):
                cleaned = cleaned[: -len(unit)]
                break
        if not cleaned:
            return None
        if _DIGITS_AND_DOT.match(cleaned):
            num = float(cleaned)
            return int(num) if num.is_integer() else num
        return value  # unparseable — preserve so the constraint check flags it
    return None
