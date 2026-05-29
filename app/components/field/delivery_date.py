"""DeliveryDateExtractor — spec-driven extraction of per-PLI delivery dates.

Column finalization scores every candidate column with
`score_column_for_canonical(spec=DELIVERY_DATE_SPEC, strips=bag.date_strips)`
and picks the highest scorer above `_COLUMN_FLOOR`. A DateStrip
confirms a column carrying genuine date cells (vs free-text columns
that just happen to be labelled "Delivery").

Confidence ladder:
  HIGH    header + date_strip
  MEDIUM  header only
"""
from __future__ import annotations

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.field._helpers import parse_date
from app.components.pickers.identifier_column import IdentifierColumnPicker
from app.specs import DELIVERY_DATE_SPEC
from app.tools import canvas as _canvas_tools  # noqa: F401 — registers @tool entries
from app.tools._registry import TOOL_REGISTRY


_COLUMN_FLOOR = 0.5


@component
class DeliveryDateExtractor(Component):
    """Extract `delivery_date` Findings from a ClusterAnchorBundle (vertical PLI axis)."""

    def __init__(self) -> None:
        Component.__init__(self)
        self._picker = IdentifierColumnPicker(
            spec=DELIVERY_DATE_SPEC, strips_attr_name="date_strips",
            score_floor=_COLUMN_FLOOR,
        )

    @component.output_types(findings=list[Finding])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        if bundle.hint.axes.pli_axis != "vertical":
            return {"findings": []}

        canonical = DELIVERY_DATE_SPEC.canonical
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
