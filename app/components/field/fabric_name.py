"""FabricNameExtractor — emits Finding(canonical="fabric_name") per PLI.

Fabric name is the descriptive phrase for a textile (e.g. "100% cotton
single jersey"), distinct from `fabric_code` which is the buyer's
identifier (e.g. "COT-2401"). Used only when a sheet has both a
code-leaning and a description column.
"""
from __future__ import annotations

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component


_CANONICAL = "fabric_name"


@component
class FabricNameExtractor(Component):
    """Extract `fabric_name` Findings from a ClusterAnchorBundle (vertical PLI axis)."""

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
