"""HeaderBandPicker — first concrete Picker, ports header-band detection.

Drop-in successor to `app/components/structure/resolvers/header_band.py`:

  - Candidates: text-dense rows (≥2 string cells, per `text_dense_rows`).
  - Policies:
      * prefer_spec_label_hits — phase-weighted spec-alias score
      * eliminate_empty_rows   — defensive filter
  - Adjacency: rows within ±`adjacency_window` of the anchor that also
    cleared the score floor are absorbed into the band (multi-row headers
    like DKN rows 1-3 and CB rows 2-3).

The picker emits a `HeaderBand` record and the full verdict trail. The
trail is what later phases / judges use to audit why a particular anchor
won.
"""
from __future__ import annotations

from typing import Any, Sequence

from haystack import component

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import HeaderBand, Rect
from app.components.pickers._base import Picker
from app.policies._base import PolicyVerdict
from app.policies.structure.header_band import (
    eliminate_empty_rows,
    prefer_spec_label_hits,
)
from app.tools.canvas.query import text_dense_rows


@component
class HeaderBandPicker(Picker[int]):
    """Find the header band of a tabular sheet."""

    def __init__(
        self,
        score_floor:      float = 1.0,
        phase_weights:    dict[str, float] | None = None,
        adjacency_window: int   = 2,
    ) -> None:
        self._phase_weights:    dict[str, float] | None = phase_weights
        self._adjacency_window: int                     = adjacency_window
        Picker.__init__(
            self,
            policies=[self._spec_hits_policy, eliminate_empty_rows],
            score_floor=score_floor,
        )

    def _spec_hits_policy(self, row: int, **kw: Any) -> PolicyVerdict:
        """Bound wrapper that injects the picker's phase_weights override."""
        return prefer_spec_label_hits(row, phase_weights=self._phase_weights, **kw)

    def candidates(self, canvas: GridCanvas) -> Sequence[int]:
        """Header rows are by definition text-dense; pre-filter to that set."""
        return sorted(text_dense_rows(canvas, min_str_count=2))

    @component.output_types(
        header_band=HeaderBand,
        verdicts=list[PolicyVerdict],
    )
    def run(self, canvas: GridCanvas) -> dict:
        """Pick the anchor row, absorb adjacent qualifying rows, emit a band."""
        rows = self.candidates(canvas=canvas)
        winner, verdicts = self._score_candidates(rows, canvas=canvas)
        if winner is None:
            return {"header_band": None, "verdicts": verdicts}

        band_rows = self._absorb_adjacent(winner, verdicts)
        rect = Rect(
            r0=min(band_rows),
            c0=1,
            r1=max(band_rows),
            c1=canvas.n_cols,
        )
        anchor_score = sum(v.score_delta for v in verdicts if v.candidate == winner)
        return {
            "header_band": HeaderBand(rect=rect, score=anchor_score),
            "verdicts":    verdicts,
        }

    def _absorb_adjacent(
        self,
        anchor:   int,
        verdicts: list[PolicyVerdict],
    ) -> set[int]:
        """Walk ±adjacency_window from anchor; absorb rows that also qualified."""
        per_row_score:      dict[int, float] = {}
        per_row_eliminated: dict[int, bool]  = {}
        for v in verdicts:
            per_row_score.setdefault(v.candidate, 0.0)
            per_row_score[v.candidate] += v.score_delta
            per_row_eliminated.setdefault(v.candidate, False)
            per_row_eliminated[v.candidate] |= v.eliminate

        def qualifies(row: int) -> bool:
            return (
                row in per_row_score
                and not per_row_eliminated[row]
                and per_row_score[row] >= self.score_floor
            )

        band = {anchor}
        # Walk upward.
        probe = anchor - 1
        while probe >= anchor - self._adjacency_window and qualifies(probe):
            band.add(probe)
            probe -= 1
        # Walk downward.
        probe = anchor + 1
        while probe <= anchor + self._adjacency_window and qualifies(probe):
            band.add(probe)
            probe += 1
        return band
