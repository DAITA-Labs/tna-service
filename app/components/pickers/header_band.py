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


# Dtype channel codes — mirror app/tools/canvas/build.py.
_DTYPE_INT   = 2
_DTYPE_FLOAT = 3


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

        band_rows = self._absorb_adjacent(winner, verdicts, canvas)
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
        canvas:   GridCanvas,
    ) -> set[int]:
        """Walk ±adjacency_window from anchor; absorb rows that also qualified.

        Header rows are by definition label-only — string cells naming
        the columns. A row that contains any numeric (int or float)
        cell is data, not a header. Without this guard a TNA's first
        PLI row gets swallowed by the header band because its data
        values happen to match identifier/quantity/date patterns in
        `query_all` (e.g. "131034" looks like an io_number int).
        """
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
                and not _row_has_numeric_cell(canvas, row)
            )

        band = {anchor}
        probe = anchor - 1
        while probe >= anchor - self._adjacency_window and qualifies(probe):
            band.add(probe)
            probe -= 1
        probe = anchor + 1
        while probe <= anchor + self._adjacency_window and qualifies(probe):
            band.add(probe)
            probe += 1
        return band


def _row_has_numeric_cell(canvas: GridCanvas, row: int) -> bool:
    """True if any cell on `row` (1-indexed) has int or float dtype.

    Header rows are label-only; the first numeric cell on a row is the
    cleanest signal it's data, not header. Returns False when the
    dtype channel isn't built (the picker still works, just without
    this guard).
    """
    dtype = canvas.channels.get("dtype")
    if dtype is None:
        return False
    if row < 1 or row > canvas.n_rows:
        return False
    return any(d in (_DTYPE_INT, _DTYPE_FLOAT) for d in dtype[row - 1])
