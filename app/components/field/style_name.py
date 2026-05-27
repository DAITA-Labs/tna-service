"""StyleNameExtractor — emits Finding(canonical="style_name") per PLI.

Style name is the descriptive phrase for a style (e.g. "TAVIRA WIDE LEG
JEAN"), distinct from `style_code` which is the buyer's identifier
(e.g. "S-2401"). When a sheet has BOTH a code-leaning column AND a
description column, the description lands here. When a sheet has only
one style-related column it ALWAYS goes to `style_code` (the *_code >
*_name priority rule baked into the spec catalog).

This extractor reads its own candidate column if present and emits
nothing otherwise. Deriving a name from a code (lookup) is a separate
concern handled downstream.
"""
from __future__ import annotations

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component


_CANONICAL = "style_name"


@component
class StyleNameExtractor(Component):
    """Extract `style_name` Findings from a ClusterAnchorBundle (vertical PLI axis)."""

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
                value=str(raw).strip(),
                confidence=Confidence.MEDIUM,
                evidence=["HEADER_BAND_MEMBER", "DTYPE_MATCH"],
            ))
        return {"findings": findings}
