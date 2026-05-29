"""PliAxisPicker — pick the PLI layout axis (sheet/sectional/vertical/horizontal).

Drop-in successor to `_decide_pli_axis` in `app/components/structure/axis_inferrer.py`.
Same inputs, same outputs (axis string + confidence). Same decision rules,
decomposed into four orthogonal policies.

Confidence:
  - 0.9 when at least one policy boosted the winning candidate
  - 0.5 when no policy fired (fallback: 'vertical')
"""
from __future__ import annotations

from typing import Any, Sequence

from haystack import component

from app.components.pickers._base import Picker
from app.policies._base import PolicyVerdict
from app.policies.structure.pli_axis import (
    prefer_horizontal_when_more_cols_than_rows,
    prefer_sectional_for_repeating_groups,
    prefer_sheet_for_kv_blocks,
    prefer_vertical_when_more_rows_than_cols,
)


_CANDIDATES: tuple[str, ...] = ("sheet", "sectional", "vertical", "horizontal")
_FALLBACK_AXIS:      str    = "vertical"
_FALLBACK_CONFIDENCE: float = 0.5
_HIGH_CONFIDENCE:    float  = 0.9


@component
class PliAxisPicker(Picker[str]):
    """Pick the PLI layout axis from structural signals."""

    def __init__(self) -> None:
        Picker.__init__(
            self,
            policies=[
                prefer_sheet_for_kv_blocks,
                prefer_sectional_for_repeating_groups,
                prefer_vertical_when_more_rows_than_cols,
                prefer_horizontal_when_more_cols_than_rows,
            ],
            # Score floor stays at 0.0 so we can fall back deterministically
            # when no policy fires (matches legacy behaviour).
            score_floor=0.0,
        )

    def candidates(self, **_: Any) -> Sequence[str]:
        return _CANDIDATES

    @component.output_types(
        pli_axis=str,
        confidence=float,
        verdicts=list[PolicyVerdict],
    )
    def run(
        self,
        kv_count:        int,
        repeating_count: int,
        n_data_rows:     int,
        n_data_cols:     int,
        sheet_size:      int,
    ) -> dict:
        winner, verdicts = self._score_candidates(
            self.candidates(),
            kv_count=kv_count,
            repeating_count=repeating_count,
            n_data_rows=n_data_rows,
            n_data_cols=n_data_cols,
            sheet_size=sheet_size,
        )
        if winner is None or _no_policy_fired(verdicts):
            return {
                "pli_axis":   _FALLBACK_AXIS,
                "confidence": _FALLBACK_CONFIDENCE,
                "verdicts":   verdicts,
            }
        return {
            "pli_axis":   winner,
            "confidence": _HIGH_CONFIDENCE,
            "verdicts":   verdicts,
        }


def _no_policy_fired(verdicts: list[PolicyVerdict]) -> bool:
    """True when every verdict scored 0.0 — fallback to 'vertical' with low confidence."""
    return all(v.score_delta == 0.0 for v in verdicts)
