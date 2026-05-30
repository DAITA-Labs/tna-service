"""PlanAssembler — turn picker outputs into a CanvasPlan.

Runs an `IdentifierColumnPicker` per identifier-shaped canonical (from
`IDENTIFIER_PICKER_CONFIGS`) and assembles one `FieldLocation` per
column-located canonical. Emits a `CanvasPlan` carrying:

  - cluster_id + anchor_sheet_name + pli_axis (from the bundle)
  - pli_rows (from the bundle's data row ranges)
  - field_locations (one FieldLocation per identifier canonical)

Stages and metadata are deferred to follow-on PRs (StagesPicker +
MetadataPicker); this PR lands the identifier half of the plan.

Scope assumption: this initial implementation handles `pli_axis = ROW`
(vertical tabular layout). Other axes (COLUMN-axis, SHEET_IS_PLI,
SECTION_PER_PLI) follow the same shape with `read_direction` flipped;
the registry-driven loop stays identical.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.plan import CanvasPlan, FieldLocation
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.pickers.identifier_column import IdentifierColumnPicker
from app.components.pickers.identifier_picker_registry import (
    IDENTIFIER_PICKER_CONFIGS,
)
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.pli_axis import PliAxis
from app.enums.read_direction import ReadDirection
from app.policies._base import PolicyVerdict


_COLUMN_FLOOR = 0.5


@component
class PlanAssembler(Component):
    """Build a CanvasPlan from a ClusterAnchorBundle by running every
    registered identifier picker."""

    def __init__(self, score_floor: float = _COLUMN_FLOOR) -> None:
        Component.__init__(self)
        self._score_floor = score_floor

    @component.output_types(plan=CanvasPlan)
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        pli_axis = _resolve_pli_axis(bundle.hint.axes.pli_axis)
        rows     = _resolve_pli_rows(bundle)

        field_locations: dict[str, FieldLocation] = {}
        all_verdicts:    list[PolicyVerdict]      = []

        for canonical, (spec, strips_attr) in IDENTIFIER_PICKER_CONFIGS.items():
            location, verdicts = self._locate_canonical(
                bundle, canonical, spec, strips_attr, rows,
            )
            field_locations[canonical] = location
            all_verdicts.extend(verdicts)

        return {
            "plan": CanvasPlan(
                cluster_id=bundle.cluster.cluster_id,
                anchor_sheet_name=bundle.anchor_sheet_name,
                pli_axis=pli_axis,
                pli_rows=rows,
                field_locations=field_locations,
                all_verdicts=all_verdicts,
            ),
        }

    def _locate_canonical(
        self,
        bundle:        ClusterAnchorBundle,
        canonical:     str,
        spec,
        strips_attr:   str,
        rows:          list[int],
    ) -> tuple[FieldLocation, list[PolicyVerdict]]:
        """Run one canonical's picker; return (FieldLocation, verdict trail)."""
        columns = bundle.hint.candidate_columns.get(canonical, [])
        picker  = IdentifierColumnPicker(
            spec=spec, strips_attr_name=strips_attr,
            score_floor=self._score_floor,
        )
        col_idx, score, verdicts = picker.pick(
            canvas=bundle.canvas, bag=bundle.bag,
            columns=columns, rows=rows,
        )
        if col_idx is None:
            location = FieldLocation(
                canonical=canonical,
                mode=FieldLocationMode.MISSING,
                scope=FieldScope.PLI,
                read_direction=ReadDirection.SAME_ROW,
                score=0.0,
                verdicts=list(verdicts),
            )
        else:
            location = FieldLocation(
                canonical=canonical,
                mode=FieldLocationMode.COLUMN,
                scope=FieldScope.PLI,
                read_direction=ReadDirection.SAME_ROW,
                column=col_idx,
                score=score,
                verdicts=list(verdicts),
            )
        return location, verdicts


# ── helpers ─────────────────────────────────────────────────────────────────


def _resolve_pli_axis(raw: str) -> PliAxis:
    """Map the legacy axis string carried on LayoutHint to the new PliAxis enum."""
    mapping = {
        "vertical":    PliAxis.ROW,
        "horizontal":  PliAxis.COLUMN,
        "sheet":       PliAxis.WHOLE_SHEET,
        "sectional":   PliAxis.SECTION,
    }
    return mapping.get(raw, PliAxis.ROW)


def _resolve_pli_rows(bundle: ClusterAnchorBundle) -> list[int]:
    """Flatten DataRowRanges from the hint into a 1-indexed list of row numbers."""
    rows: list[int] = []
    for rng in bundle.hint.data_row_ranges:
        rows.extend(range(rng.row_start, rng.row_end + 1))
    return rows
