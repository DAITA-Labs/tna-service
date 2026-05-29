"""IdentifierColumnPicker — parametric picker for per-canonical column selection.

NOT a Haystack `@component` — used as an internal helper by the
per-canonical extractor components (IoNumberExtractor, QuantityExtractor,
etc.). Keeping it un-decorated avoids the "no components calling
components" anti-pattern: the extractor stays a component and reaches
for the picker as deterministic logic.

The picker is parametric on `spec` (a FieldSpec) and `strips_attr_name`
(the name of the `StructureBag` attribute that carries the relevant
strip type — e.g., "same_length_strips" for io_number, "int_strips"
for quantity). One picker per canonical at construction time;
extractors hold theirs as instance state.
"""
from __future__ import annotations

from typing import Any, Sequence

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import StructureBag
from app.components.pickers._base import Picker
from app.policies._base import PolicyVerdict
from app.policies.field.identifier import score_column_via_spec


class IdentifierColumnPicker(Picker[int]):
    """Pick the best column for one canonical from `hint.candidate_columns`."""

    def __init__(
        self,
        spec:              Any,
        strips_attr_name:  str,
        score_floor:       float = 0.5,
    ) -> None:
        self._spec:             Any = spec
        self._strips_attr_name: str = strips_attr_name
        Picker.__init__(
            self,
            policies=[score_column_via_spec],
            score_floor=score_floor,
        )

    def candidates(self, columns: list[int]) -> Sequence[int]:  # type: ignore[override]
        return list(columns)

    def pick(
        self,
        canvas:  GridCanvas,
        bag:     StructureBag,
        columns: list[int],
        rows:    list[int],
    ) -> tuple[int | None, float, list[PolicyVerdict]]:
        """Return (winning_column_or_none, score, verdict_trail).

        Empty columns / rows short-circuit to (None, 0.0, []).
        """
        if not columns or not rows:
            return None, 0.0, []
        strips = getattr(bag, self._strips_attr_name)
        winner, verdicts = self._score_candidates(
            self.candidates(columns),
            canvas=canvas,
            rows=rows,
            spec=self._spec,
            strips=strips,
        )
        if winner is None:
            return None, 0.0, verdicts
        score = sum(v.score_delta for v in verdicts if v.candidate == winner)
        return winner, score, verdicts
