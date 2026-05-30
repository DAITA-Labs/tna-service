"""PlanAssembler — assemble a CanvasPlan from per-canonical scoreboards + stages.

Four phases (the scoreboard architecture in code):

  1. Per-canonical scoring — run one `IdentifierPicker` per registered
     identifier canonical, collect every candidate's score into the
     global scoreboard. No winners picked yet.
  2. Cross-field review — `PlanCrossFieldPicker` reads the global
     scoreboard and emits plan-level verdicts + `ValidationWarning`s.
     (Future iterations may also mutate scoreboard scores; today the
     two policies are validation-style.)
  3. Winner selection — for each canonical, take the argmax non-eliminated
     candidate above the score floor; build the matching `FieldLocation`
     dispatching on the winner's `mode`. Missing canonicals get
     `FieldLocation(mode=MISSING)`.
  4. Stages assembly — `StagesAssembler` runs the multi-winner stage band
     flow (every band above the floor survives) and produces a
     `list[StageBandPlan]` that lands on `CanvasPlan.stage_bands`.

Output: `CanvasPlan` carrying field_locations, stage_bands, scoreboards,
all_verdicts, warnings, and the rest. The CanvasApplier (planned)
consumes this plan to produce `list[PLI]`.

Metadata is deferred to a follow-on PR.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.finding import ValidationWarning
from app.artifacts.plan import (
    CanvasPlan,
    FieldLocation,
    LocationCandidate,
)
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.pickers.identifier import IdentifierPicker
from app.components.pickers.identifier_picker_registry import (
    IDENTIFIER_PICKER_CONFIGS,
)
from app.components.pickers.plan_cross_field import PlanCrossFieldPicker
from app.components.plan.stages_assembler import StagesAssembler
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.pli_axis import PliAxis
from app.enums.read_direction import ReadDirection
from app.policies._base import PolicyVerdict


_COLUMN_FLOOR = 0.5

# Per-canonical scoreboard entry shape.
ScoreEntry = tuple[LocationCandidate, float, bool]


@component
class PlanAssembler(Component):
    """Run IdentifierPickers + PlanCrossFieldPicker; emit a CanvasPlan."""

    def __init__(self, score_floor: float = _COLUMN_FLOOR) -> None:
        Component.__init__(self)
        self._score_floor          = score_floor
        self._cross_field_picker   = PlanCrossFieldPicker()
        self._stages_assembler     = StagesAssembler(score_floor=score_floor)

    @component.output_types(plan=CanvasPlan)
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        pli_axis = _resolve_pli_axis(bundle.hint.axes.pli_axis)
        rows     = _resolve_pli_rows(bundle)

        scoreboards, per_canonical_verdicts = self._collect_scoreboards(bundle, rows)
        cross_verdicts, warnings            = self._cross_field_picker.review(
            scoreboards, score_floor=self._score_floor,
        )
        field_locations = self._select_winners(scoreboards)

        stages_out      = self._stages_assembler.run(bundle=bundle)
        stage_bands     = stages_out["stage_bands"]
        stage_verdicts  = stages_out["verdicts"]

        return {
            "plan": CanvasPlan(
                cluster_id=bundle.cluster.cluster_id,
                anchor_sheet_name=bundle.anchor_sheet_name,
                pli_axis=pli_axis,
                pli_rows=rows,
                field_locations=field_locations,
                stage_bands=stage_bands,
                all_verdicts=per_canonical_verdicts + cross_verdicts + stage_verdicts,
                warnings=warnings,
                scoreboards=scoreboards,
            ),
        }

    def _collect_scoreboards(
        self,
        bundle: ClusterAnchorBundle,
        rows:   list[int],
    ) -> tuple[dict[str, list[ScoreEntry]], list[PolicyVerdict]]:
        """Phase 1 — score every candidate per canonical; return global scoreboard."""
        scoreboards: dict[str, list[ScoreEntry]] = {}
        all_verdicts: list[PolicyVerdict]        = []
        for canonical, (spec, strips_attr) in IDENTIFIER_PICKER_CONFIGS.items():
            picker = IdentifierPicker(
                spec=spec,
                strips_attr_name=strips_attr,
                score_floor=self._score_floor,
            )
            scoreboard, verdicts = picker.score_all_locations(
                canvas=bundle.canvas, bag=bundle.bag,
                hint=bundle.hint, canonical=canonical, rows=rows,
            )
            scoreboards[canonical] = scoreboard
            all_verdicts.extend(verdicts)
        return scoreboards, all_verdicts

    def _select_winners(
        self,
        scoreboards: dict[str, list[ScoreEntry]],
    ) -> dict[str, FieldLocation]:
        """Phase 3 — argmax per canonical; build FieldLocation per winner."""
        out: dict[str, FieldLocation] = {}
        for canonical, scoreboard in scoreboards.items():
            winner = _argmax_above_floor(scoreboard, self._score_floor)
            out[canonical] = _build_field_location(canonical, winner)
        return out


# ── helpers ─────────────────────────────────────────────────────────────────


def _argmax_above_floor(
    scoreboard:  list[ScoreEntry],
    score_floor: float,
) -> tuple[LocationCandidate, float] | None:
    """Top non-eliminated candidate whose score clears the floor; else None."""
    surviving = [(c, s) for c, s, elim in scoreboard if not elim and s >= score_floor]
    if not surviving:
        return None
    return max(surviving, key=lambda pair: pair[1])


def _build_field_location(
    canonical: str,
    winner:    tuple[LocationCandidate, float] | None,
) -> FieldLocation:
    """Build a `FieldLocation` from the winning candidate (or MISSING when none)."""
    if winner is None:
        return FieldLocation(
            canonical=canonical,
            mode=FieldLocationMode.MISSING,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_ROW,
        )
    candidate, score = winner
    if candidate.mode == FieldLocationMode.COLUMN:
        return FieldLocation(
            canonical=canonical,
            mode=FieldLocationMode.COLUMN,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_ROW,
            column=candidate.column,
            score=score,
        )
    if candidate.mode == FieldLocationMode.ROW:
        return FieldLocation(
            canonical=canonical,
            mode=FieldLocationMode.ROW,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_COLUMN,
            row=candidate.row,
            score=score,
        )
    if candidate.mode == FieldLocationMode.KV_BLOCK:
        return FieldLocation(
            canonical=canonical,
            mode=FieldLocationMode.KV_BLOCK,
            scope=FieldScope.SHEET,
            read_direction=ReadDirection.FIXED,
            kv_block=candidate.kv_block,
            score=score,
        )
    return FieldLocation(
        canonical=canonical,
        mode=FieldLocationMode.MISSING,
        scope=FieldScope.PLI,
        read_direction=ReadDirection.SAME_ROW,
    )


def _resolve_pli_axis(raw: str) -> PliAxis:
    """Map the legacy axis string on LayoutHint to the PliAxis enum."""
    return {
        "vertical":   PliAxis.ROW,
        "horizontal": PliAxis.COLUMN,
        "sheet":      PliAxis.WHOLE_SHEET,
        "sectional":  PliAxis.SECTION,
    }.get(raw, PliAxis.ROW)


def _resolve_pli_rows(bundle: ClusterAnchorBundle) -> list[int]:
    """Flatten DataRowRanges from the hint into a 1-indexed list of row numbers."""
    rows: list[int] = []
    for rng in bundle.hint.data_row_ranges:
        rows.extend(range(rng.row_start, rng.row_end + 1))
    return rows
