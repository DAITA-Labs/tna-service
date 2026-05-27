"""IO-number extractor — emits Finding(canonical="io_number") per PLI.

The IO number is a per-PLI identifier (also called job no, internal
order, PO no depending on the spreadsheet author). Raw values may be
typed by openpyxl as int, float, or string; the postprocess hook
coerces all three back to a string since IO numbers are identifiers
not numerics. Floats with a `.0` fractional part are emitted without
the trailing zero.
"""
from __future__ import annotations

from typing import Any

from haystack import component

from app.artifacts.finding import Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.field._base import BaseCanonicalComponent


class IoNumberComponent(BaseCanonicalComponent):
    """Extract `io_number` Findings from a ClusterAnchorBundle."""

    canonical = "io_number"

    def _postprocess(self, value: Any) -> str:
        """Coerce numeric io codes back to strings; strip whitespace from string codes."""
        if isinstance(value, bool):  # bool is a subclass of int — handle separately
            return str(value)
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return str(int(value)) if value.is_integer() else str(value)
        return str(value).strip()


@component
class IoNumberExtractor(Component):
    """Haystack wrapper around `IoNumberComponent.extract_findings`.

    Inputs:
        bundle — a ClusterAnchorBundle

    Outputs:
        findings — list[Finding] with canonical='io_number'
    """

    def __init__(self) -> None:
        Component.__init__(self)
        self._extractor = IoNumberComponent()

    @component.output_types(findings=list[Finding])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        return {"findings": self._extractor.extract_findings(bundle)}
