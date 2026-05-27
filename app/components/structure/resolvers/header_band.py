"""HeaderBandResolver — find the contiguous header rows of a tabular layout.

Combines three signals to score each row:
  - spec-alias hits per phase (identifier/stage/subfield/metadata)
  - bold-cell density
  - fill-colour density

The top-scoring row becomes the header band's anchor. If adjacent rows
(±1, ±2) also score above threshold, they're absorbed into the same
band (multi-row headers — DKN rows 1-3, CB rows 2-3).

Emits a single HeaderBand record into the bag. If no row scores above
`min_score`, emits None (the sheet has no tabular header — likely
SHEET_IS_PLI or empty).
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import HeaderBand, Rect, StructureBag
from app.tools.canvas.query import find_header_rows_via_specs


_BAND_ADJACENCY_WINDOW = 2
_MIN_SCORE = 1.0


def resolve_header_band(canvas: GridCanvas,
                        bag: StructureBag,
                        min_score: float = _MIN_SCORE) -> HeaderBand | None:
    """Identify the header band of a tabular sheet; mutate `bag.header_band`.

    Returns the same HeaderBand it wrote (or None when no row scored
    high enough). Idempotent — calling twice yields the same result.
    """
    scored = find_header_rows_via_specs(canvas, min_score=min_score)
    if not scored:
        bag.header_band = None
        return None

    anchor_row, anchor_score, _ = scored[0]
    band_rows = _absorb_adjacent_scored_rows(anchor_row, scored)

    rect = Rect(
        r0=min(band_rows),
        c0=1,
        r1=max(band_rows),
        c1=canvas.n_cols,
    )
    header_band = HeaderBand(rect=rect, score=anchor_score)
    bag.header_band = header_band
    return header_band


def _absorb_adjacent_scored_rows(anchor_row: int,
                                  scored: list[tuple[int, float, dict]]) -> set[int]:
    """Walk outward from `anchor_row`, absorbing scored rows in a contiguous band."""
    scored_set = {row for row, _, _ in scored}
    band_rows = {anchor_row}

    # Walk upward
    candidate = anchor_row - 1
    while candidate >= anchor_row - _BAND_ADJACENCY_WINDOW and candidate in scored_set:
        band_rows.add(candidate)
        candidate -= 1
    # Walk downward
    candidate = anchor_row + 1
    while candidate <= anchor_row + _BAND_ADJACENCY_WINDOW and candidate in scored_set:
        band_rows.add(candidate)
        candidate += 1
    return band_rows
