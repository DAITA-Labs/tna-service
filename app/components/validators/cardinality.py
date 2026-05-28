"""CardinalityValidator — mandatory-canonical coverage check.

Every PLI row in the data zone must carry a Finding for every canonical
flagged as mandatory in the spec catalog (currently `io_number` and
`quantity`). When a row is missing one, the validator emits an `error`
ValidationWarning naming the row and the missing canonical.

The validator runs AFTER the identifier extractors + arbiter — it
inspects the combined Findings list and the PLI row set carried by the
LayoutHint. Findings for non-mandatory canonicals are ignored.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.finding import Finding, ValidationWarning
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.specs import MANDATORY_IDENTIFIERS


@component
class CardinalityValidator(Component):
    """Emit a ValidationWarning per (PLI row, mandatory canonical) missing a Finding."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(warnings=list[ValidationWarning])
    def run(self, findings: list[Finding], bundle: ClusterAnchorBundle) -> dict:
        pli_rows = _pli_rows(bundle)
        if not pli_rows:
            return {"warnings": []}

        warnings: list[ValidationWarning] = []
        for canonical in MANDATORY_IDENTIFIERS:
            rows_with_finding = {
                f.value_coord[1] for f in findings if f.canonical == canonical
            }
            for row in sorted(pli_rows - rows_with_finding):
                warnings.append(ValidationWarning(
                    name=f"missing_mandatory_{canonical}",
                    severity="error",
                    message=(
                        f"PLI row {row} has no `{canonical}` finding — "
                        f"spec catalog flags this canonical as mandatory."
                    ),
                ))
        return {"warnings": warnings}


def _pli_rows(bundle: ClusterAnchorBundle) -> set[int]:
    """Flatten DataRowRanges from the hint into a set of 1-indexed row numbers."""
    rows: set[int] = set()
    for rng in bundle.hint.data_row_ranges:
        rows.update(range(rng.row_start, rng.row_end + 1))
    return rows
