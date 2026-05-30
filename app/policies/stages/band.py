"""Band-level stage policies — score one StageBand at a time."""
from __future__ import annotations

from typing import Any

from app.artifacts.structure import StageBand
from app.policies._base import PolicyVerdict


def score_band_detected(
    candidate: StageBand,
    **_:       Any,
) -> PolicyVerdict:
    """Every band the resolver emitted starts with score 1.0.

    Trust signal: if the existing resolver picked this band out of the
    canvas, it's a band candidate worth considering. Cross-band
    policies (anchor row, no overlap) can knock the score down later.
    """
    return PolicyVerdict(
        name="score_band_detected",
        candidate=candidate,
        score_delta=1.0,
        message=f"detected: {candidate.name_text!r}",
    )
