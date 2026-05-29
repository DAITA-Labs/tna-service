"""SubfieldAxisPicker — pick the subfield layout axis (implicit/horizontal).

Drop-in successor to `_decide_subfield_axis` in axis_inferrer.py.
Confidence: HIGH when the implicit (no bands) branch fires OR when a
horizontal merge overlaps the first band; LOW when we fall back to
'horizontal' without merge evidence.
"""
from __future__ import annotations

from typing import Any, Sequence

from haystack import component

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import StructureBag
from app.components.pickers._base import Picker
from app.policies._base import PolicyVerdict
from app.policies.structure.subfield_axis import (
    prefer_horizontal_when_band_has_overlapping_horiz_merge,
    prefer_implicit_when_no_stage_bands,
)


_CANDIDATES: tuple[str, ...] = ("implicit", "horizontal")
_HIGH_CONFIDENCE: float      = 0.9
_LOW_CONFIDENCE:  float      = 0.5


@component
class SubfieldAxisPicker(Picker[str]):
    """Pick the subfield layout axis from canvas + bag signals."""

    def __init__(self) -> None:
        Picker.__init__(
            self,
            policies=[
                prefer_implicit_when_no_stage_bands,
                prefer_horizontal_when_band_has_overlapping_horiz_merge,
            ],
            score_floor=0.0,
        )

    def candidates(self, **_: Any) -> Sequence[str]:
        return _CANDIDATES

    @component.output_types(
        subfield_axis=str,
        confidence=float,
        verdicts=list[PolicyVerdict],
    )
    def run(self, canvas: GridCanvas, bag: StructureBag) -> dict:
        winner, verdicts = self._score_candidates(
            self.candidates(),
            canvas=canvas,
            bag=bag,
        )
        if winner is not None and not _no_policy_fired(verdicts):
            return {
                "subfield_axis": winner,
                "confidence":    _HIGH_CONFIDENCE,
                "verdicts":      verdicts,
            }
        # Fallback: 'horizontal' with low confidence — matches legacy.
        return {
            "subfield_axis": "horizontal",
            "confidence":    _LOW_CONFIDENCE,
            "verdicts":      verdicts,
        }


def _no_policy_fired(verdicts: list[PolicyVerdict]) -> bool:
    return all(v.score_delta == 0.0 for v in verdicts)
