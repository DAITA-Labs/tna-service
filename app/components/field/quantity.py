"""QuantityExtractor — spec-driven per-PLI numeric extraction.

Column finalization:
  The LayoutHint hands over one or more candidate columns ranked by
  header-band alias-match weight. That rank is necessary but not
  sufficient — a header labelled "Qty" may sit above a column that's
  90% blank, full of garbage strings, or carrying values outside the
  spec's valid range. So the extractor SCORES every candidate column
  (header_match + strip_overlap + dtype_match_rate + constraint_pass_rate)
  and picks the highest scorer. If even the best candidate falls below
  `_COLUMN_FLOOR`, no findings are emitted — wrong findings beat right
  findings every time.

Per-cell evidence:

  - **Header match** — column was in `hint.candidate_columns["quantity"]`.
  - **IntStrip confirmation** — column also appears in `bag.int_strips`.
  - **`QUANTITY_SPEC.value_constraints`** — `min=1, max=100000` per value.

Structural rejection:
  A value cell inside a merged range is skipped outright (no Finding) —
  merged cells at the quantity column position are labels, totals, or
  repeated-value fillers, never real per-PLI order counts.

Confidence ladder per cell (for non-rejected cells):

  HIGH    header + int_strip + constraints satisfied
  MEDIUM  header + constraints satisfied, no int_strip
  LOW     header but a constraint was violated
"""
from __future__ import annotations

import re
from typing import Any

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.specs import QUANTITY_SPEC
from app.tools import canvas as _canvas_tools  # noqa: F401 — registers @tool entries
from app.tools._registry import TOOL_REGISTRY


# Strip thousands separators (commas, spaces) and trailing unit text before
# attempting numeric parse.
_DIGITS_AND_DOT = re.compile(r"^-?\d+(\.\d+)?$")

# Minimum column-finalization score required to commit to a column.
_COLUMN_FLOOR = 0.5


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

        score_column = TOOL_REGISTRY["score_column_for_canonical"]
        check_column_has_strip = TOOL_REGISTRY["check_column_has_strip"]
        find_merged_cells_in_column = TOOL_REGISTRY["find_merged_cells_in_column"]

        # Column finalization — score every candidate, pick the highest scorer,
        # skip entirely if the best score falls below the floor.
        scored = [
            (col, score_column(
                bundle.canvas, col, rows, QUANTITY_SPEC, bundle.bag.int_strips,
            ))
            for col in columns
        ]
        col_idx, best_score = max(scored, key=lambda x: x[1])
        if best_score < _COLUMN_FLOOR:
            return {"findings": []}

        col_letter = get_column_letter(col_idx)
        band = bundle.hint.header_band
        label_coord = (col_letter, band.rect.r0 if band else 1)

        int_strip_confirmed = check_column_has_strip(bundle.bag.int_strips, col_idx, rows)
        constraints = QUANTITY_SPEC.value_constraints
        merged_cells = find_merged_cells_in_column(bundle.canvas, col_idx, rows)

        findings: list[Finding] = []
        for row in rows:
            # Structural rejection: cells inside a merged range aren't real
            # per-PLI quantities (labels, totals, repeated-value fillers).
            if (row, col_idx) in merged_cells:
                continue

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
