"""Subfield-axis policies — score subfield-axis from stage band + merge-span signals."""
from __future__ import annotations

from typing import Any

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import StructureBag
from app.policies._base import PolicyVerdict


_BOOST = 1.0


def prefer_implicit_when_no_stage_bands(
    candidate: str,
    *,
    bag:    StructureBag,
    **_:    Any,
) -> PolicyVerdict:
    """Without any StageBands there's no subfield structure to infer."""
    fits  = not bag.stage_bands
    score = _BOOST if (candidate == "implicit" and fits) else 0.0
    return PolicyVerdict(
        name="prefer_implicit_when_no_stage_bands",
        candidate=candidate,
        score_delta=score,
        message="no stage bands" if score else "",
    )


def prefer_horizontal_when_band_has_overlapping_horiz_merge(
    candidate: str,
    *,
    bag:    StructureBag,
    **_:    Any,
) -> PolicyVerdict:
    """A horizontal merge span sitting above the first stage band overlapping
    its columns implies sub-columns flow horizontally (planned/actual/qty in
    a row above each stage column)."""
    if not bag.stage_bands:
        return PolicyVerdict(
            name="prefer_horizontal_when_band_has_overlapping_horiz_merge",
            candidate=candidate,
            score_delta=0.0,
        )
    band = bag.stage_bands[0]
    has_overlap = any(
        span.orientation == "horizontal"
        and span.rect.r1 < band.rect.r0
        and span.rect.c0 <= band.rect.c1
        and span.rect.c1 >= band.rect.c0
        for span in bag.merge_spans
    )
    score = _BOOST if (candidate == "horizontal" and has_overlap) else 0.0
    return PolicyVerdict(
        name="prefer_horizontal_when_band_has_overlapping_horiz_merge",
        candidate=candidate,
        score_delta=score,
        message="horiz merge above first band" if score else "",
    )
