"""DateTrioValidator — chronological order + at-least-one presence.

Two checks per PLI row:

  1. **Chronological order** of whichever of the three date canonicals
     are present:

         ex_fty_date  ≤  shipment_date  ≤  delivery_date

     Algorithm: collect the present dates in chronological-canonical
     order, then assert the resulting sequence is monotonically
     non-decreasing. When all three are present this means two
     adjacent comparisons. When the middle (`shipment_date`) is
     missing, `ex_fty_date ≤ delivery_date` is checked directly —
     the transitivity short-circuit only applies when shipment is
     available to bridge.

     Inversions emit a `warning` (not `error`) — they can be
     legitimate (sample reshipments, air-freight bumps, clerical
     adjustments), so downstream judges decide whether to act.

  2. **At-least-one presence** from `DATE_IDENTIFIERS_AT_LEAST_ONE` —
     every PLI row must carry at least one of the three dates. A
     PLI with NO dates is an `error` (the spec catalog declares the
     trio as a group-required identifier set). This check needs the
     bundle to enumerate every PLI row, including those with zero
     date findings.
"""
from __future__ import annotations

from collections import defaultdict

from haystack import component

from app.artifacts.finding import Finding, ValidationWarning
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.specs import DATE_IDENTIFIERS_AT_LEAST_ONE


# Chronological-canonical order: factory → in-transit → buyer.
_CHRONO_ORDER = ("ex_fty_date", "shipment_date", "delivery_date")
_TRIO = set(_CHRONO_ORDER)


@component
class DateTrioValidator(Component):
    """Emit warnings per PLI for date inversions or missing-trio."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(warnings=list[ValidationWarning])
    def run(self, findings: list[Finding], bundle: ClusterAnchorBundle) -> dict:
        pli_rows = _pli_rows(bundle)

        per_row: dict[int, dict[str, Finding]] = defaultdict(dict)
        for f in findings:
            if f.canonical in _TRIO:
                per_row[f.value_coord[1]][f.canonical] = f

        warnings: list[ValidationWarning] = []

        # ── Check 1: at-least-one presence per PLI row ────────────────────
        for row in sorted(pli_rows):
            if not (per_row.get(row, {}).keys() & set(DATE_IDENTIFIERS_AT_LEAST_ONE)):
                warnings.append(ValidationWarning(
                    name="missing_date_trio",
                    severity="error",
                    message=(
                        f"PLI row {row} has none of "
                        f"{sorted(DATE_IDENTIFIERS_AT_LEAST_ONE)} — spec "
                        f"catalog requires at least one date per PLI."
                    ),
                ))

        # ── Check 2: chronological order over the present dates ───────────
        for row in sorted(per_row):
            present = [
                (canonical, per_row[row][canonical])
                for canonical in _CHRONO_ORDER
                if canonical in per_row[row]
            ]
            for i in range(len(present) - 1):
                earlier_key, earlier_f = present[i]
                later_key,   later_f   = present[i + 1]
                if earlier_f.value > later_f.value:
                    warnings.append(ValidationWarning(
                        name="date_trio_inversion",
                        severity="warning",
                        message=(
                            f"PLI row {row}: {earlier_key} ({earlier_f.value}) is "
                            f"after {later_key} ({later_f.value}) — dates should "
                            f"be chronological."
                        ),
                        affects_findings=[earlier_f, later_f],
                    ))
        return {"warnings": warnings}


def _pli_rows(bundle: ClusterAnchorBundle) -> set[int]:
    """Flatten DataRowRanges from the hint into a set of 1-indexed row numbers."""
    rows: set[int] = set()
    for rng in bundle.hint.data_row_ranges:
        rows.update(range(rng.row_start, rng.row_end + 1))
    return rows
