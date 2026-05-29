"""ShipmentDateExtractor — spec-driven extraction of per-PLI shipment dates.

Same shape as DeliveryDateExtractor / ExFtyDateExtractor — header rank,
DateStrip confirmation. See `delivery_date.py` for the explanatory
docstring.
"""
from __future__ import annotations

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.field._helpers import parse_date
from app.components.pickers.identifier_column import IdentifierColumnPicker
from app.specs import SHIPMENT_DATE_SPEC
from app.tools import canvas as _canvas_tools  # noqa: F401 — registers @tool entries
from app.tools._registry import TOOL_REGISTRY


_COLUMN_FLOOR = 0.5


@component
class ShipmentDateExtractor(Component):
    """Extract `shipment_date` Findings from a ClusterAnchorBundle (vertical PLI axis)."""

    def __init__(self) -> None:
        Component.__init__(self)
        self._picker = IdentifierColumnPicker(
            spec=SHIPMENT_DATE_SPEC, strips_attr_name="date_strips",
            score_floor=_COLUMN_FLOOR,
        )

    @component.output_types(findings=list[Finding])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        if bundle.hint.axes.pli_axis != "vertical":
            return {"findings": []}

        canonical = SHIPMENT_DATE_SPEC.canonical
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
            bundle.bag.date_strips, col_idx, rows,
        )

        findings: list[Finding] = []
        for row in rows:
            raw = bundle.canvas.cell_values[row - 1][col_idx - 1]
            parsed = parse_date(raw)
            if parsed is None:
                continue

            evidence: list[str] = ["HEADER_BAND_MEMBER"]
            if strip_confirmed:
                evidence.append("DATE_STRIP_CONFIRMED")
                confidence = Confidence.HIGH
            else:
                confidence = Confidence.MEDIUM

            findings.append(Finding(
                canonical=canonical,
                label_coord=label_coord,
                value_coord=(col_letter, row),
                value=parsed,
                confidence=confidence,
                evidence=evidence,
            ))
        return {"findings": findings}
