"""resolve_header_band — thin facade over `HeaderBandPicker`.

Identifies the contiguous header rows of a tabular layout. Internally
delegates to `HeaderBandPicker`, which decomposes the scoring into
composable policies (see `app/components/pickers/header_band.py`).

Kept as a function (rather than swapping the call site to the picker
directly) so existing `populate_semantics` chaining and tests stay
unchanged. New code should consume `HeaderBandPicker` directly.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import HeaderBand, StructureBag
from app.components.pickers.header_band import HeaderBandPicker


_MIN_SCORE = 1.0


def resolve_header_band(
    canvas:    GridCanvas,
    bag:       StructureBag,
    min_score: float = _MIN_SCORE,
) -> HeaderBand | None:
    """Identify the header band; write it onto `bag.header_band`.

    Returns the same HeaderBand it wrote (or None when no row qualified).
    Idempotent.
    """
    picker = HeaderBandPicker(score_floor=min_score)
    result = picker.run(canvas=canvas)
    header_band = result["header_band"]
    bag.header_band = header_band
    return header_band
