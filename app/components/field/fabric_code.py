"""FabricCodeExtractor — spec-driven extraction of fabric identifier codes.

Same shape as StyleCodeExtractor / ColorCodeExtractor — header rank,
SameLengthStrip confirmation, optional value constraints. See
`style_code.py` for the explanatory docstring.
"""
from __future__ import annotations

from typing import Any

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.pickers.identifier_column import IdentifierColumnPicker
from app.specs import FABRIC_CODE_SPEC
from app.tools import canvas as _canvas_tools  # noqa: F401 — registers @tool entries
from app.tools._registry import TOOL_REGISTRY


_COLUMN_FLOOR = 0.5


@component
class FabricCodeExtractor(Component):
    """Extract `fabric_code` Findings from a ClusterAnchorBundle (vertical PLI axis)."""

    def __init__(self) -> None:
        Component.__init__(self)
        self._picker = IdentifierColumnPicker(
            spec=FABRIC_CODE_SPEC, strips_attr_name="same_length_strips",
            score_floor=_COLUMN_FLOOR,
        )

    @component.output_types(findings=list[Finding])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        if bundle.hint.axes.pli_axis != "vertical":
            return {"findings": []}

        canonical = FABRIC_CODE_SPEC.canonical
        columns = bundle.hint.candidate_columns.get(canonical, [])
        rows = bundle.hint.candidate_rows.get(canonical, [])

        col_idx, _score, _verdicts = self._picker.pick(
            canvas=bundle.canvas, bag=bundle.bag,
            columns=columns, rows=rows,
        )
        if col_idx is None:
            return {"findings": []}

        check_column_has_strip = TOOL_REGISTRY["check_column_has_strip"]

        col_letter = get_column_letter(col_idx)
        band = bundle.hint.header_band
        label_coord = (col_letter, band.rect.r0 if band else 1)

        strip_confirmed = check_column_has_strip(
            bundle.bag.same_length_strips, col_idx, rows,
        )

        findings: list[Finding] = []
        for row in rows:
            raw = bundle.canvas.cell_values[row - 1][col_idx - 1]
            if raw is None or raw == "":
                continue
            value = _coerce_code(raw)

            evidence: list[str] = ["HEADER_BAND_MEMBER"]
            if strip_confirmed:
                evidence.append("SAME_LENGTH_STRIP_CONFIRMED")
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


def _coerce_code(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value).strip()
