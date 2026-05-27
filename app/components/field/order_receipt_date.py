"""OrderReceiptDateExtractor — sheet-level metadata: the date the order was received.

Reads `bundle.hint.candidate_kv_blocks["order_receipt_date"]`. The
value cell is parsed through `parse_date` (same helper the date
identifier extractors use). Emits one Finding per sheet, or zero
when the value isn't a parseable date.
"""
from __future__ import annotations

from typing import Any

from haystack import component
from openpyxl.utils import column_index_from_string

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.field._helpers import parse_date
from app.specs import ORDER_RECEIPT_DATE_SPEC


@component
class OrderReceiptDateExtractor(Component):
    """Extract `order_receipt_date` Finding from a ClusterAnchorBundle's KvBlocks."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(findings=list[Finding])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        canonical = ORDER_RECEIPT_DATE_SPEC.canonical
        candidates = bundle.hint.candidate_kv_blocks.get(canonical, [])
        if not candidates:
            return {"findings": []}

        kv = candidates[0]
        raw = _read_value(bundle, kv.value_coord)
        if raw is None:
            return {"findings": []}

        parsed = parse_date(raw)
        if parsed is None:
            return {"findings": []}

        return {"findings": [Finding(
            canonical=canonical,
            label_coord=kv.label_coord,
            value_coord=kv.value_coord,
            value=parsed,
            confidence=Confidence.MEDIUM,
            evidence=["KV_BLOCK_MATCH"],
        )]}


def _read_value(bundle: ClusterAnchorBundle, coord: tuple[str, int]) -> Any:
    col_letter, row = coord
    col_idx = column_index_from_string(col_letter)
    raw = bundle.canvas.cell_values[row - 1][col_idx - 1]
    if raw is None or raw == "":
        return None
    return raw
