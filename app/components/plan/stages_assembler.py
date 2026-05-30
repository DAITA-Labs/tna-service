"""StagesAssembler — produce a list[StageBandPlan] from the stage band scoreboard.

Three phases:

  1. Score every detected `StageBand` via `StageBandPicker` (multi-winner
     by design — every band above the score floor survives).
  2. Threshold selection: keep all surviving bands above the floor.
  3. Per-band attribute resolution:
       - `canonical` from exact alias match against `STAGE_SPECS`
       - `subfield_axis` from the sheet-level `LayoutHint.axes.subfield_axis`
       - `read_direction` from the sheet's `PliAxis` (SAME_ROW for ROW_PER_PLI;
         FIXED for SHEET_IS_PLI; etc.)
       - `subfield_indices` (TODO) — map subfield-cluster coords to
         `planned_date / actual_date / qty / …` keys. Empty today;
         population lands when the subfield-cluster mapping helper is built.

Output: `list[StageBandPlan]`. Wiring into PlanAssembler follows in a
later PR — this PR ships the assembler in isolation.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.plan import StageBandPlan
from app.artifacts.structure import StageBand
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.pickers.stage_band import StageBandPicker
from app.enums.field_scope import FieldScope
from app.enums.read_direction import ReadDirection
from app.enums.subfield_axis import SubfieldAxis
from app.policies._base import PolicyVerdict
from app.specs import STAGE_SPECS


_DEFAULT_FLOOR = 0.5


@component
class StagesAssembler(Component):
    """Produce a list of StageBandPlans from the detected stage bands."""

    def __init__(self, score_floor: float = _DEFAULT_FLOOR) -> None:
        Component.__init__(self)
        self._score_floor: float           = score_floor
        self._picker:      StageBandPicker = StageBandPicker(score_floor=score_floor)

    @component.output_types(
        stage_bands=list[StageBandPlan],
        verdicts=list[PolicyVerdict],
    )
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        scoreboard, verdicts = self._picker.score_all_bands(bundle.bag)
        survivors            = _survivors(scoreboard, self._score_floor)

        subfield_axis    = _resolve_subfield_axis(bundle.hint.axes.subfield_axis)
        scope            = _resolve_scope_for_stages(bundle.hint.axes.pli_axis)
        read_direction   = _resolve_read_direction(bundle.hint.axes.pli_axis)

        stage_bands: list[StageBandPlan] = []
        for band, score in survivors:
            stage_bands.append(_build_stage_band_plan(
                band=band, score=score,
                subfield_axis=subfield_axis,
                scope=scope,
                read_direction=read_direction,
                verdicts=verdicts,
            ))

        return {"stage_bands": stage_bands, "verdicts": verdicts}


# ── helpers ────────────────────────────────────────────────────────────────


def _survivors(
    scoreboard:  list[tuple[StageBand, float, bool]],
    score_floor: float,
) -> list[tuple[StageBand, float]]:
    """Every non-eliminated band scoring above the floor."""
    return [
        (band, score) for band, score, eliminated in scoreboard
        if not eliminated and score >= score_floor
    ]


def _build_stage_band_plan(
    *,
    band:           StageBand,
    score:          float,
    subfield_axis:  SubfieldAxis,
    scope:          FieldScope,
    read_direction: ReadDirection,
    verdicts:       list[PolicyVerdict],
) -> StageBandPlan:
    """Build one StageBandPlan from a surviving band + sheet-level axes."""
    canonical    = _match_canonical(band.name_text)
    anchor_col_letter, anchor_row = band.name_coord
    anchor_coord                  = (anchor_row, _col_letter_to_index(anchor_col_letter))
    band_verdicts = [v for v in verdicts if v.candidate == band]
    return StageBandPlan(
        name=band.name_text,
        canonical=canonical,
        anchor_coord=anchor_coord,
        anchor_rect=band.rect,
        scope=scope,
        subfield_axis=subfield_axis,
        read_direction=read_direction,
        subfield_indices={},   # TODO: populate from bag.subfield_clusters
        score=score,
        verdicts=band_verdicts,
    )


def _match_canonical(name_text: str) -> str | None:
    """Exact case-insensitive match against every STAGE_SPECS alias."""
    needle = (name_text or "").strip().lower()
    if not needle:
        return None
    for spec in STAGE_SPECS:
        if needle in {alias.lower() for alias in spec.aliases}:
            return spec.canonical
    return None


def _resolve_subfield_axis(raw: str) -> SubfieldAxis:
    return {
        "horizontal": SubfieldAxis.HORIZONTAL,
        "vertical":   SubfieldAxis.VERTICAL,
        "implicit":   SubfieldAxis.IMPLICIT,
        "none":       SubfieldAxis.NONE,
    }.get(raw, SubfieldAxis.HORIZONTAL)


def _resolve_scope_for_stages(pli_axis_raw: str) -> FieldScope:
    """Stages typically scope-match the PLI iteration axis."""
    if pli_axis_raw == "sheet":
        return FieldScope.SHEET
    if pli_axis_raw == "sectional":
        return FieldScope.GROUP
    return FieldScope.PLI


def _resolve_read_direction(pli_axis_raw: str) -> ReadDirection:
    if pli_axis_raw == "sheet":
        return ReadDirection.FIXED
    if pli_axis_raw == "sectional":
        return ReadDirection.OFFSET
    if pli_axis_raw == "horizontal":
        return ReadDirection.SAME_COLUMN
    return ReadDirection.SAME_ROW


def _col_letter_to_index(letter: str) -> int:
    """A → 1, B → 2, … AA → 27. (openpyxl-style column letter to 1-indexed int.)"""
    n = 0
    for ch in letter.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n
