"""StageAxisPicker — pick the stage layout axis (horizontal/vertical/none/unknown).

Drop-in successor to `_decide_stage_axis` in axis_inferrer.py.
Confidence logic mirrors the legacy function:

  pli_axis = sheet              → HIGH regardless of which branch wins
  pli_axis in (vertical, sectional):
      a date-strip branch fires → HIGH
      no branch fires           → 'none' with LOW
  pli_axis = anything else      → 'unknown' with LOW
"""
from __future__ import annotations

from typing import Any, Sequence

from haystack import component

from app.components.pickers._base import Picker
from app.policies._base import PolicyVerdict
from app.policies.structure.stage_axis import (
    prefer_horizontal_when_sheet_with_horiz_date_strips,
    prefer_horizontal_when_tabular_with_vert_date_strips,
    prefer_vertical_when_sheet_with_vert_date_strips,
    prefer_vertical_when_tabular_with_horiz_date_strips,
)


_CANDIDATES: tuple[str, ...] = ("horizontal", "vertical", "none", "unknown")
_HIGH_CONFIDENCE: float      = 0.9
_LOW_CONFIDENCE:  float      = 0.5


@component
class StageAxisPicker(Picker[str]):
    """Pick the stage layout axis given pli_axis + date-strip counts."""

    def __init__(self) -> None:
        Picker.__init__(
            self,
            policies=[
                prefer_horizontal_when_sheet_with_horiz_date_strips,
                prefer_vertical_when_sheet_with_vert_date_strips,
                prefer_horizontal_when_tabular_with_vert_date_strips,
                prefer_vertical_when_tabular_with_horiz_date_strips,
            ],
            score_floor=0.0,
        )

    def candidates(self, **_: Any) -> Sequence[str]:
        return _CANDIDATES

    @component.output_types(
        stage_axis=str,
        confidence=float,
        verdicts=list[PolicyVerdict],
    )
    def run(
        self,
        pli_axis:    str,
        vert_dates:  int,
        horiz_dates: int,
    ) -> dict:
        winner, verdicts = self._score_candidates(
            self.candidates(),
            pli_axis=pli_axis,
            vert_dates=vert_dates,
            horiz_dates=horiz_dates,
        )

        if winner is not None and not _no_policy_fired(verdicts):
            return {
                "stage_axis": winner,
                "confidence": _HIGH_CONFIDENCE,
                "verdicts":   verdicts,
            }
        # Fallback: match legacy behaviour exactly.
        if pli_axis == "sheet":
            # All three sheet branches return high confidence; the 'none' default
            # for sheet is HIGH.
            return {"stage_axis": "none", "confidence": _HIGH_CONFIDENCE, "verdicts": verdicts}
        if pli_axis in ("vertical", "sectional"):
            return {"stage_axis": "none", "confidence": _LOW_CONFIDENCE, "verdicts": verdicts}
        return {"stage_axis": "unknown", "confidence": _LOW_CONFIDENCE, "verdicts": verdicts}


def _no_policy_fired(verdicts: list[PolicyVerdict]) -> bool:
    """True when every verdict scored 0.0."""
    return all(v.score_delta == 0.0 for v in verdicts)
