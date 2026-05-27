"""IoNumberExtractor — spec-driven per-PLI identifier extraction.

Column finalization scores every candidate column with
`score_column_for_canonical(spec=IO_NUMBER_SPEC, strips=bag.same_length_strips)`
and picks the highest scorer above `_COLUMN_FLOOR`. A SameLengthStrip
confirms a column whose cells share a uniform character length —
exactly the shape an identifier slot has when every PLI has the same
brand-issued IO format.

Per-cell evidence:

  - Header match — column is in `hint.candidate_columns["io_number"]`.
  - SameLengthStrip confirmation — `bag.same_length_strips` covers the
    column + data rows.
  - `IO_NUMBER_SPEC.value_constraints.max_len = 30` — an IO that
    exceeds 30 chars is suspect (descriptions sneaking into an id
    column).

Confidence ladder per cell:

  HIGH    header + same_length_strip + constraints satisfied
  MEDIUM  header + constraints satisfied, no same_length_strip
  LOW     header but constraint violated
"""
from __future__ import annotations

from typing import Any

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.specs import IO_NUMBER_SPEC
from app.tools import canvas as _canvas_tools  # noqa: F401 — registers @tool entries
from app.tools._registry import TOOL_REGISTRY


_COLUMN_FLOOR = 0.5


@component
class IoNumberExtractor(Component):
    """Extract `io_number` Findings from a ClusterAnchorBundle (vertical PLI axis)."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(findings=list[Finding])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        if bundle.hint.axes.pli_axis != "vertical":
            return {"findings": []}

        canonical = IO_NUMBER_SPEC.canonical
        columns = bundle.hint.candidate_columns.get(canonical, [])
        rows = bundle.hint.candidate_rows.get(canonical, [])
        if not columns or not rows:
            return {"findings": []}

        score_column = TOOL_REGISTRY["score_column_for_canonical"]
        check_column_has_strip = TOOL_REGISTRY["check_column_has_strip"]

        scored = [
            (col, score_column(
                bundle.canvas, col, rows, IO_NUMBER_SPEC, bundle.bag.same_length_strips,
            ))
            for col in columns
        ]
        col_idx, best_score = max(scored, key=lambda x: x[1])
        if best_score < _COLUMN_FLOOR:
            return {"findings": []}

        col_letter = get_column_letter(col_idx)
        band = bundle.hint.header_band
        label_coord = (col_letter, band.rect.r0 if band else 1)

        strip_confirmed = check_column_has_strip(
            bundle.bag.same_length_strips, col_idx, rows,
        )
        constraints = IO_NUMBER_SPEC.value_constraints

        findings: list[Finding] = []
        for row in rows:
            raw = bundle.canvas.cell_values[row - 1][col_idx - 1]
            if raw is None or raw == "":
                continue
            value = _coerce_io_code(raw)

            evidence: list[str] = ["HEADER_BAND_MEMBER"]
            if strip_confirmed:
                evidence.append("SAME_LENGTH_STRIP_CONFIRMED")

            breach = _check_constraints(value, constraints)
            if breach is not None:
                evidence.append(f"CONSTRAINT:{breach}")
                confidence = Confidence.LOW
            elif strip_confirmed:
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
    """Return a constraint-name token if violated, else None."""
    if isinstance(value, str):
        length = len(value)
        if constraints.min_len is not None and length < constraints.min_len:
            return "below_min_len"
        if constraints.max_len is not None and length > constraints.max_len:
            return "above_max_len"
    return None


def _coerce_io_code(value: Any) -> str:
    """Normalise raw cell value to an IO-code string."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value).strip()
