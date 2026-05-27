"""ColorNameExtractor — spec-driven extraction of descriptive color phrases.

Three signals combine to produce each Finding (same shape as
StyleNameExtractor / FabricNameExtractor):

  1. **Header match** — `hint.candidate_columns["color_name"]`.
  2. **LongTextStrip confirmation** — `bag.long_text_strips`.
  3. **`COLOR_NAME_SPEC.value_constraints`** — `min_len` / `max_len`.

Confidence ladder per cell:
  HIGH    header + long_text_strip + constraints satisfied
  MEDIUM  header + constraints satisfied, no long_text_strip
  LOW     header but constraint violated
"""
from __future__ import annotations

from typing import Any

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.specs import COLOR_NAME_SPEC
from app.tools import canvas as _canvas_tools  # noqa: F401 — registers @tool entries
from app.tools._registry import TOOL_REGISTRY


@component
class ColorNameExtractor(Component):
    """Extract `color_name` Findings from a ClusterAnchorBundle (vertical PLI axis)."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(findings=list[Finding])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        if bundle.hint.axes.pli_axis != "vertical":
            return {"findings": []}

        canonical = COLOR_NAME_SPEC.canonical
        columns = bundle.hint.candidate_columns.get(canonical, [])
        rows = bundle.hint.candidate_rows.get(canonical, [])
        if not columns or not rows:
            return {"findings": []}

        check_column_has_strip = TOOL_REGISTRY["check_column_has_strip"]

        col_idx = columns[0]
        col_letter = get_column_letter(col_idx)
        band = bundle.hint.header_band
        label_coord = (col_letter, band.rect.r0 if band else 1)

        long_text_confirmed = check_column_has_strip(
            bundle.bag.long_text_strips, col_idx, rows,
        )
        constraints = COLOR_NAME_SPEC.value_constraints

        findings: list[Finding] = []
        for row in rows:
            raw = bundle.canvas.cell_values[row - 1][col_idx - 1]
            if raw is None or raw == "":
                continue
            value = str(raw).strip()
            if not value:
                continue

            evidence: list[str] = ["HEADER_BAND_MEMBER"]
            if long_text_confirmed:
                evidence.append("LONG_TEXT_STRIP_CONFIRMED")

            breach = _check_constraints(value, constraints)
            if breach is not None:
                evidence.append(f"CONSTRAINT:{breach}")
                confidence = Confidence.LOW
            elif long_text_confirmed:
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
    if constraints.min_len is not None and len(value) < constraints.min_len:
        return "below_min_len"
    if constraints.max_len is not None and len(value) > constraints.max_len:
        return "above_max_len"
    return None
