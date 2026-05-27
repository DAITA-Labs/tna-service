"""FactoryExtractor — sheet-level metadata: manufacturing factory / unit name.

Reads `bundle.hint.candidate_kv_blocks["factory"]`. Emits one Finding
per sheet.
"""
from __future__ import annotations

from typing import Any

from haystack import component
from openpyxl.utils import column_index_from_string

from app.artifacts.finding import Confidence, Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.specs import FACTORY_SPEC


@component
class FactoryExtractor(Component):
    """Extract `factory` Finding from a ClusterAnchorBundle's KvBlocks."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(findings=list[Finding])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        canonical = FACTORY_SPEC.canonical
        candidates = bundle.hint.candidate_kv_blocks.get(canonical, [])
        if not candidates:
            return {"findings": []}

        kv = candidates[0]
        value = _read_value(bundle, kv.value_coord)
        if value is None:
            return {"findings": []}

        return {"findings": [Finding(
            canonical=canonical,
            label_coord=kv.label_coord,
            value_coord=kv.value_coord,
            value=str(value).strip(),
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
