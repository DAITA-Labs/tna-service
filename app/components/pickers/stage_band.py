"""StageBandPicker — score every detected StageBand for multi-winner selection.

Unlike per-canonical pickers (one winner per canonical), the stages flow
keeps every band scoring above a threshold. Callers should use
`score_all_bands()` and apply their own threshold — `pick()` (argmax)
is intentionally not the primary entry point here.

Picker[StageBand] base provides candidate-loop + policy aggregation;
this subclass just supplies `candidates()` (read from the bag) and
exposes a typed `score_all_bands()` accessor.
"""
from __future__ import annotations

from typing import Any, Sequence

from app.artifacts.structure import StageBand, StructureBag
from app.components.pickers._base import Picker
from app.policies._base import PolicyVerdict
from app.policies.stages.band import score_band_detected


class StageBandPicker(Picker[StageBand]):
    """Score every detected stage band; supports multi-winner selection by threshold."""

    def __init__(self, score_floor: float = 0.5) -> None:
        Picker.__init__(
            self,
            policies=[score_band_detected],
            score_floor=score_floor,
        )

    def candidates(self, bag: StructureBag, **_: Any) -> Sequence[StageBand]:
        return list(bag.stage_bands)

    def score_all_bands(
        self,
        bag: StructureBag,
    ) -> tuple[list[tuple[StageBand, float, bool]], list[PolicyVerdict]]:
        """Scoreboard of every detected band. Caller thresholds for survivors."""
        return self._score_all_candidates(self.candidates(bag=bag), bag=bag)
