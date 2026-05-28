"""StageSequenceValidator — per-PLI stage plan_dates follow catalog order.

For each PLI's `FinalStage`s, the validator:

  1. Filters to stages with a known `canonical` (matched a STAGE_SPECS
     alias) AND a non-null `plan_date`. Skipped stages get separate
     treatment:
        - `canonical is None` (open-vocab novel label) → emit an
          `info`-level `unrecognised_stage` warning so operators see
          which novel labels recur across sheets. The validator can't
          place a novel stage in chronological order — but flagging it
          drives growth of the STAGE_SPECS alias catalog.
        - `plan_date is None` (metadata-only stage) → silent skip,
          nothing to compare.

  2. Sorts the remaining stages by `(sequence_hint_bucket, spec_index)`,
     where:
        - `sequence_hint_bucket` maps `early → 1`, `middle → 2`,
          `late → 3` per the spec catalog's `StageSpec.sequence_hint`.
        - `spec_index` is the stage's position in `STAGE_SPECS` — a
          stable secondary key for stages sharing a bucket.

  3. Walks the sorted sequence and emits a `warning` for every adjacent
     pair whose `plan_date`s are out of chronological order. Inversions
     downgrade to `warning` (not `error`) because real TNA flows do
     legitimately reshuffle stages (sample fast-tracks, fit cycles,
     reworks).
"""
from __future__ import annotations

from haystack import component

from app.artifacts.finding import ValidationWarning
from app.components._base import Component
from app.specs import STAGE_SPECS
from app.specs.schemas import FinalStage


# Bucket ranks: early < middle < late. Empty hint falls to the end.
_BUCKET_RANK = {"early": 1, "middle": 2, "late": 3, "": 4}

# Pre-build the (bucket_rank, spec_index) priority for each known canonical
# so the validator does O(1) lookups inside the per-PLI loop.
_PRIORITY: dict[str, tuple[int, int]] = {
    spec.canonical: (_BUCKET_RANK[spec.sequence_hint], idx)
    for idx, spec in enumerate(STAGE_SPECS)
}


@component
class StageSequenceValidator(Component):
    """Emit `warning`s for per-PLI stage plan_date inversions in catalog order."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(warnings=list[ValidationWarning])
    def run(self, stages_per_row: dict[int, list[FinalStage]]) -> dict:
        warnings: list[ValidationWarning] = []
        for row in sorted(stages_per_row):
            stages = stages_per_row[row]

            # Surface novel (open-vocab) stages so operators can grow the
            # STAGE_SPECS catalog. `info` severity — not blocking, just
            # observability.
            for s in stages:
                if s.canonical is None and s.name:
                    warnings.append(ValidationWarning(
                        name="unrecognised_stage",
                        severity="info",
                        message=(
                            f"PLI row {row}: stage `{s.name}` did not match "
                            f"any STAGE_SPECS alias — sequence not validated. "
                            f"Consider adding to the catalog if it recurs."
                        ),
                    ))

            # Filter to stages with known canonical + plan_date set, decorate
            # with priority for sorting. `_PRIORITY` is built from every
            # STAGE_SPECS entry, so any non-None canonical is guaranteed to
            # have a priority — no defensive check needed.
            sortable = sorted(
                (
                    (_PRIORITY[s.canonical], s)
                    for s in stages
                    if s.canonical is not None and s.plan_date is not None
                ),
                key=lambda x: x[0],
            )

            # Walk adjacent pairs in sorted order; flag any inversion.
            for i in range(len(sortable) - 1):
                _, earlier = sortable[i]
                _, later = sortable[i + 1]
                if earlier.plan_date > later.plan_date:
                    warnings.append(ValidationWarning(
                        name="stage_sequence_inversion",
                        severity="warning",
                        message=(
                            f"PLI row {row}: stage `{earlier.canonical}` "
                            f"(plan_date={earlier.plan_date}) is after stage "
                            f"`{later.canonical}` (plan_date={later.plan_date}) "
                            f"— catalog order expects the reverse."
                        ),
                    ))
        return {"warnings": warnings}
