"""StyleCodeExtractor — emits Finding(canonical="style_code") per PLI.

Style codes are per-PLI string identifiers issued by the brand/buyer
(e.g. "S-2401", "FW26-1207"). openpyxl may type a purely-numeric style
code as int/float — we coerce back to a string identifier and strip
whitespace on string-typed cells.
"""
from __future__ import annotations

from typing import Any

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component


_CANONICAL = "style_code"


@component
class StyleCodeExtractor(Component):
    """Extract `style_code` Findings from a ClusterAnchorBundle (vertical PLI axis)."""

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
            if raw is None or raw == "":
                continue
            findings.append(Finding(
                canonical=_CANONICAL,
                label_coord=label_coord,
                value_coord=(col_letter, row),
                value=_coerce_code(raw),
                confidence=Confidence.MEDIUM,
                evidence=["HEADER_BAND_MEMBER", "DTYPE_MATCH"],
            ))
        return {"findings": findings}


def _coerce_code(value: Any) -> str:
    """Normalise raw cell value into an identifier-code string."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value).strip()
