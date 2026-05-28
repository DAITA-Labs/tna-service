"""CanvasValidatorOrchestrator — runs every canvas-architecture validator.

A single entry point for the validator chain. Owns one instance of each
validator and calls them in a fixed order, concatenating their warnings.
The ordering is stable — same input always produces warnings in the
same sequence, which downstream judges and replay tooling rely on.

Order follows the spec catalog: presence checks first (cardinality,
row alignment, date trio), then structural cross-checks against the
detected geometry (stage wins, stage structure), then per-column
quality checks (quantity dtype) and stage-sequence sanity. New
validators get appended; never inserted in the middle.

Stage-specific validators (`StageSequenceValidator`) take a separate
`stages_per_row` input — when no stages were extracted, pass an empty
dict (or omit; it defaults to empty). The orchestrator delegates the
"no input → no warnings" semantics to the underlying validator.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.finding import Finding, ValidationWarning
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.validators.cardinality import CardinalityValidator
from app.components.validators.date_trio import DateTrioValidator
from app.components.validators.quantity_dtype import QuantityDtypeValidator
from app.components.validators.row_alignment import RowAlignmentValidator
from app.components.validators.stage_sequence import StageSequenceValidator
from app.components.validators.stage_structure import StageStructureValidator
from app.components.validators.stage_wins import StageWinsValidator
from app.specs.schemas import FinalStage


@component
class CanvasValidatorOrchestrator(Component):
    """Run every canvas-arch validator and return the concatenated warnings."""

    def __init__(self) -> None:
        Component.__init__(self)
        self._cardinality = CardinalityValidator()
        self._row_alignment = RowAlignmentValidator()
        self._date_trio = DateTrioValidator()
        self._stage_wins = StageWinsValidator()
        self._stage_structure = StageStructureValidator()
        self._quantity_dtype = QuantityDtypeValidator()
        self._stage_sequence = StageSequenceValidator()

    @component.output_types(warnings=list[ValidationWarning])
    def run(
        self,
        findings: list[Finding],
        bundle: ClusterAnchorBundle,
        stages_per_row: dict[int, list[FinalStage]] | None = None,
    ) -> dict:
        stages = stages_per_row or {}

        warnings: list[ValidationWarning] = []
        warnings.extend(self._cardinality.run(findings=findings, bundle=bundle)["warnings"])
        warnings.extend(self._row_alignment.run(findings=findings, bundle=bundle)["warnings"])
        warnings.extend(self._date_trio.run(findings=findings, bundle=bundle)["warnings"])
        warnings.extend(self._stage_wins.run(findings=findings, bundle=bundle)["warnings"])
        warnings.extend(self._stage_structure.run(bundle=bundle)["warnings"])
        warnings.extend(self._quantity_dtype.run(findings=findings, bundle=bundle)["warnings"])
        warnings.extend(self._stage_sequence.run(stages_per_row=stages)["warnings"])
        return {"warnings": warnings}
