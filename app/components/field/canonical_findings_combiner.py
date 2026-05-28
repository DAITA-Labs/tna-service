"""CanonicalFindingsCombiner — concatenate per-canonical extractor outputs.

Each per-canonical extractor (IoNumberExtractor, QuantityExtractor, etc.)
emits its own `findings: list[Finding]` socket. The downstream
`IdentifierArbiter` consumes a single `findings: list[Finding]` input.
This combiner is the pure-data bridge — receives one socket per
canonical, concatenates them, emits one combined list.

Same pattern as `CanvasWarningAggregator` in the validators pipeline:
no other component is called, just data plumbing through pipeline edges.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.finding import Finding
from app.components._base import Component


@component
class CanonicalFindingsCombiner(Component):
    """Concatenate every per-canonical extractor's findings into one list."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(findings=list[Finding])
    def run(
        self,
        io_number_findings:     list[Finding],
        quantity_findings:      list[Finding],
        style_code_findings:    list[Finding],
        color_code_findings:    list[Finding],
        fabric_code_findings:   list[Finding],
        style_name_findings:    list[Finding],
        color_name_findings:    list[Finding],
        fabric_name_findings:   list[Finding],
        delivery_date_findings: list[Finding],
        shipment_date_findings: list[Finding],
        ex_fty_date_findings:   list[Finding],
    ) -> dict:
        return {"findings": [
            *io_number_findings,
            *quantity_findings,
            *style_code_findings,
            *color_code_findings,
            *fabric_code_findings,
            *style_name_findings,
            *color_name_findings,
            *fabric_name_findings,
            *delivery_date_findings,
            *shipment_date_findings,
            *ex_fty_date_findings,
        ]}
