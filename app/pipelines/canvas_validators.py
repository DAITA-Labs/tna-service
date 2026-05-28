"""Canvas-architecture validators pipeline factory.

Wires every canvas validator into a single Haystack `Pipeline`. The
pipeline ingests `findings`, `bundle`, and `stages_per_row` on its
edge sockets; each validator runs on its own inputs in parallel; the
`CanvasWarningAggregator` collects every validator's `warnings`
output and concatenates them in chain order.

Chain order (presence first, geometry next, column-quality last):

  1. cardinality
  2. row_alignment
  3. date_trio
  4. stage_wins
  5. stage_structure
  6. quantity_dtype
  7. stage_sequence

The order is fixed because downstream judges and replay tooling
expect a stable warning sequence. Append new validators to the end.
"""
from __future__ import annotations

from haystack import Pipeline

from app.components.validators.canvas_warning_aggregator import CanvasWarningAggregator
from app.components.validators.cardinality import CardinalityValidator
from app.components.validators.date_trio import DateTrioValidator
from app.components.validators.quantity_dtype import QuantityDtypeValidator
from app.components.validators.row_alignment import RowAlignmentValidator
from app.components.validators.stage_sequence import StageSequenceValidator
from app.components.validators.stage_structure import StageStructureValidator
from app.components.validators.stage_wins import StageWinsValidator


def make_canvas_validators_pipeline() -> Pipeline:
    """Return a Haystack Pipeline wiring every canvas validator + the aggregator.

    Pipeline inputs (set by the caller via `pipeline.run({...})`):
      - cardinality.findings, cardinality.bundle
      - row_alignment.findings, row_alignment.bundle
      - date_trio.findings, date_trio.bundle
      - stage_wins.findings, stage_wins.bundle
      - stage_structure.bundle
      - quantity_dtype.findings, quantity_dtype.bundle
      - stage_sequence.stages_per_row

    Pipeline output: `pipeline.run(...)["aggregator"]["warnings"]`.
    """
    pipeline = Pipeline()
    pipeline.add_component("cardinality",      CardinalityValidator())
    pipeline.add_component("row_alignment",    RowAlignmentValidator())
    pipeline.add_component("date_trio",        DateTrioValidator())
    pipeline.add_component("stage_wins",       StageWinsValidator())
    pipeline.add_component("stage_structure",  StageStructureValidator())
    pipeline.add_component("quantity_dtype",   QuantityDtypeValidator())
    pipeline.add_component("stage_sequence",   StageSequenceValidator())
    pipeline.add_component("aggregator",       CanvasWarningAggregator())

    pipeline.connect("cardinality.warnings",      "aggregator.cardinality_warnings")
    pipeline.connect("row_alignment.warnings",    "aggregator.row_alignment_warnings")
    pipeline.connect("date_trio.warnings",        "aggregator.date_trio_warnings")
    pipeline.connect("stage_wins.warnings",       "aggregator.stage_wins_warnings")
    pipeline.connect("stage_structure.warnings",  "aggregator.stage_structure_warnings")
    pipeline.connect("quantity_dtype.warnings",   "aggregator.quantity_dtype_warnings")
    pipeline.connect("stage_sequence.warnings",   "aggregator.stage_sequence_warnings")

    return pipeline
