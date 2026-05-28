"""RowAlignmentValidator — non-mandatory canonicals should cover the same rows.

`CardinalityValidator` handles mandatory canonicals (`io_number`,
`quantity`) — every PLI row must carry one. This validator covers the
distinct case for *non-mandatory* canonicals: when a canonical's
findings cover the majority of PLI rows (≥ `_COVERAGE_THRESHOLD`) but
not all of them, the missing rows are almost certainly extraction
misses, not legitimate absences.

Below the threshold the column is treated as legitimately sparse
(e.g. a sheet where only some PLIs carry a style_code) and no
warnings are emitted.
"""
from __future__ import annotations

from collections import defaultdict

from haystack import component

from app.artifacts.finding import Finding, ValidationWarning
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.specs import MANDATORY_IDENTIFIERS


# A canonical covering ≥70% of PLI rows is treated as "expected on every
# row" — the missing rows then surface as `row_alignment_gap` warnings.
_COVERAGE_THRESHOLD = 0.7


@component
class RowAlignmentValidator(Component):
    """Emit a warning per (row, canonical) where a majority-covered canonical is missing."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(warnings=list[ValidationWarning])
    def run(self, findings: list[Finding], bundle: ClusterAnchorBundle) -> dict:
        return {"warnings": _check_majority_canonical_coverage(findings, bundle)}


def _check_majority_canonical_coverage(
    findings: list[Finding],
    bundle: ClusterAnchorBundle,
) -> list[ValidationWarning]:
    """Flag missing rows for non-mandatory canonicals that cover the majority.

    For each non-mandatory canonical in `findings`, compute the row
    coverage over the PLI row set. When coverage exceeds the threshold,
    every missing row surfaces as a `row_alignment_gap` warning.
    """
    pli_rows = _pli_rows(bundle)
    if not pli_rows:
        return []

    rows_by_canonical: dict[str, set[int]] = defaultdict(set)
    for f in findings:
        if f.canonical in MANDATORY_IDENTIFIERS:
            continue
        rows_by_canonical[f.canonical].add(f.value_coord[1])

    warnings: list[ValidationWarning] = []
    for canonical in sorted(rows_by_canonical):
        rows = rows_by_canonical[canonical] & pli_rows
        coverage = len(rows) / len(pli_rows)
        if coverage <= _COVERAGE_THRESHOLD or coverage >= 1.0:
            continue
        for row in sorted(pli_rows - rows):
            warnings.append(ValidationWarning(
                name="row_alignment_gap",
                severity="warning",
                message=(
                    f"PLI row {row} has no `{canonical}` finding, but "
                    f"`{canonical}` covers {len(rows)}/{len(pli_rows)} PLI "
                    f"rows ({coverage:.0%}) — likely an extraction miss "
                    f"rather than legitimate absence."
                ),
            ))
    return warnings


def _pli_rows(bundle: ClusterAnchorBundle) -> set[int]:
    """Flatten DataRowRanges from the hint into a set of 1-indexed row numbers."""
    rows: set[int] = set()
    for rng in bundle.hint.data_row_ranges:
        rows.update(range(rng.row_start, rng.row_end + 1))
    return rows
