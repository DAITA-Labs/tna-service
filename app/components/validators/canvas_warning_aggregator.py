"""CanvasWarningAggregator — concatenates every canvas validator's warnings.

Pure data — receives seven warning lists through the pipeline's edges
and emits one combined list. No other component is called. Adding a
new validator means adding one input socket here and one
`pipeline.connect()` line in `make_canvas_validators_pipeline`.

Concatenation order matches the socket declaration order in `run`:
cardinality → row_alignment → date_trio → stage_wins → stage_structure
→ quantity_dtype → stage_sequence. Downstream judges and replay
tooling rely on this stable sequence.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.finding import ValidationWarning
from app.components._base import Component


@component
class CanvasWarningAggregator(Component):
    """Concatenate every canvas validator's warnings into a single list."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(warnings=list[ValidationWarning])
    def run(
        self,
        cardinality_warnings:    list[ValidationWarning],
        row_alignment_warnings:  list[ValidationWarning],
        date_trio_warnings:      list[ValidationWarning],
        stage_wins_warnings:     list[ValidationWarning],
        stage_structure_warnings: list[ValidationWarning],
        quantity_dtype_warnings: list[ValidationWarning],
        stage_sequence_warnings: list[ValidationWarning],
    ) -> dict:
        return {"warnings": [
            *cardinality_warnings,
            *row_alignment_warnings,
            *date_trio_warnings,
            *stage_wins_warnings,
            *stage_structure_warnings,
            *quantity_dtype_warnings,
            *stage_sequence_warnings,
        ]}
