"""IdentifierPicker — unified picker across COLUMN / ROW / KV_BLOCK modes.

Successor to `IdentifierColumnPicker` for the plan-driven path. Scores
`LocationCandidate` instances drawn from all three hint sources
(`candidate_columns`, `candidate_rows`, `candidate_kv_blocks`) in one
pass; the winning candidate's `mode` tells `PlanAssembler` which
`FieldLocation` shape to construct.

NOT a Haystack `@component`. Used as an internal helper by PlanAssembler
to honour `feedback_no_components_calling_components`.

Construction per canonical:
  IdentifierPicker(spec=IO_NUMBER_SPEC,
                    strips_attr_name="same_length_strips",
                    score_floor=0.5)

Each instance owns its spec + the StructureBag attribute its column /
row policies read for confirmation strips.

`IdentifierColumnPicker` stays in place for the legacy findings-path
extractors; this picker is the new code's entry point.
"""
from __future__ import annotations

from typing import Any, Sequence

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutHint
from app.artifacts.plan import LocationCandidate
from app.artifacts.structure import StructureBag
from app.components.pickers._base import Picker
from app.enums.field_location_mode import FieldLocationMode
from app.policies._base import PolicyVerdict
from app.policies.field.identifier import (
    score_lc_column_via_spec,
    score_lc_kv_via_label_match,
    score_lc_row_via_spec,
)


class IdentifierPicker(Picker[LocationCandidate]):
    """Pick the best location across COLUMN / ROW / KV_BLOCK modes for one canonical."""

    def __init__(
        self,
        spec:             Any,
        strips_attr_name: str,
        score_floor:      float = 0.5,
    ) -> None:
        Picker.__init__(
            self,
            policies=[
                score_lc_column_via_spec,
                score_lc_row_via_spec,
                score_lc_kv_via_label_match,
            ],
            score_floor=score_floor,
        )
        self._spec:             Any = spec
        self._strips_attr_name: str = strips_attr_name

    def candidates(
        self,
        hint:      LayoutHint,
        canonical: str,
        **_:       Any,
    ) -> Sequence[LocationCandidate]:
        """Collect candidates from all three hint sources, tagged by mode."""
        out: list[LocationCandidate] = []
        for col in hint.candidate_columns.get(canonical, []):
            out.append(LocationCandidate(mode=FieldLocationMode.COLUMN, column=col))
        for row in hint.candidate_rows.get(canonical, []):
            out.append(LocationCandidate(mode=FieldLocationMode.ROW, row=row))
        for kv in hint.candidate_kv_blocks.get(canonical, []):
            out.append(LocationCandidate(mode=FieldLocationMode.KV_BLOCK, kv_block=kv))
        return out

    def pick(
        self,
        canvas:    GridCanvas,
        bag:       StructureBag,
        hint:      LayoutHint,
        canonical: str,
        rows:      list[int],
        cols:      list[int] | None = None,
    ) -> tuple[LocationCandidate | None, float, list[PolicyVerdict]]:
        """Return `(winner, score, verdicts)`.

        Empty candidate set → `(None, 0.0, [])`. Winner-below-floor →
        `(None, 0.0, verdicts)`.
        """
        cands = self.candidates(hint=hint, canonical=canonical)
        if not cands:
            return None, 0.0, []
        strips = getattr(bag, self._strips_attr_name)
        winner, verdicts = self._score_candidates(
            cands,
            canvas=canvas,
            rows=rows,
            cols=cols or [],
            spec=self._spec,
            strips=strips,
        )
        if winner is None:
            return None, 0.0, verdicts
        score = sum(v.score_delta for v in verdicts if v.candidate == winner)
        return winner, score, verdicts

    def score_all_locations(
        self,
        canvas:    GridCanvas,
        bag:       StructureBag,
        hint:      LayoutHint,
        canonical: str,
        rows:      list[int],
        cols:      list[int] | None = None,
    ) -> tuple[list[tuple[LocationCandidate, float, bool]], list[PolicyVerdict]]:
        """Public scoreboard accessor — every candidate's score + elimination flag.

        Used by PlanAssembler to populate the global scoreboard before
        cross-field mutators run; used by the LLM judge for full-context
        introspection.
        """
        cands  = self.candidates(hint=hint, canonical=canonical)
        strips = getattr(bag, self._strips_attr_name)
        return self._score_all_candidates(
            cands,
            canvas=canvas,
            rows=rows,
            cols=cols or [],
            spec=self._spec,
            strips=strips,
        )
