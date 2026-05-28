"""DateTrioValidator — chronological order of the three per-PLI dates.

Every PLI row that carries multiple date findings should satisfy:

    ex_fty_date  ≤  shipment_date  ≤  delivery_date

  - `ex_fty_date`  is when goods leave the factory
  - `shipment_date` is when goods are loaded (in-transit)
  - `delivery_date` is when goods arrive at the buyer

Out-of-order pairs emit a `warning` (not `error`) — inversions can be
legitimate in unusual flows (sample reshipments, air-freight bumps,
clerical adjustments), so downstream judges decide whether to act.
Only the two adjacent comparisons are checked; the third is implied by
transitivity, and emitting it separately would duplicate warnings when
all three are out of order.

Findings without all three dates trigger no check — partial data is
expected during early order-cycle stages.
"""
from __future__ import annotations

from collections import defaultdict

from haystack import component

from app.artifacts.finding import Finding, ValidationWarning
from app.components._base import Component


_TRIO = ("ex_fty_date", "shipment_date", "delivery_date")


@component
class DateTrioValidator(Component):
    """Emit a `warning` per PLI row whose ex_fty / shipment / delivery dates invert."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(warnings=list[ValidationWarning])
    def run(self, findings: list[Finding]) -> dict:
        # Bucket findings by PLI row, keeping only the three trio canonicals.
        # When multiple findings exist for the same canonical on the same row
        # (the IdentifierArbiter should have deduped earlier), the latest one
        # in iteration order wins — semantically equivalent because the arbiter
        # already picked one.
        per_row: dict[int, dict[str, Finding]] = defaultdict(dict)
        for f in findings:
            if f.canonical in _TRIO:
                per_row[f.value_coord[1]][f.canonical] = f

        warnings: list[ValidationWarning] = []
        for row in sorted(per_row):
            dates = per_row[row]
            for earlier_key, later_key in (
                ("ex_fty_date", "shipment_date"),
                ("shipment_date", "delivery_date"),
            ):
                earlier = dates.get(earlier_key)
                later = dates.get(later_key)
                if earlier is None or later is None:
                    continue
                if earlier.value > later.value:
                    warnings.append(ValidationWarning(
                        name="date_trio_inversion",
                        severity="warning",
                        message=(
                            f"PLI row {row}: {earlier_key} ({earlier.value}) is "
                            f"after {later_key} ({later.value}) — dates should be "
                            f"chronological."
                        ),
                        affects_findings=[earlier, later],
                    ))
        return {"warnings": warnings}
