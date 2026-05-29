"""Stage-axis policies — score each stage-axis option from date-strip + pli-axis signals.

StageAxis depends on PliAxis: the thresholds and which orientation wins
change based on whether the sheet is SHEET_IS_PLI or tabular. Each
policy encodes one branch of the legacy `_decide_stage_axis` decision.
"""
from __future__ import annotations

from typing import Any

from app.policies._base import PolicyVerdict


# Thresholds — mirror axis_inferrer.py exactly.
_DATE_STRIPS_FOR_SHEET_STAGE   = 2
_DATE_STRIPS_FOR_TABULAR_STAGE = 3

_BOOST = 1.0


def prefer_horizontal_when_sheet_with_horiz_date_strips(
    candidate: str,
    *,
    pli_axis:    str,
    horiz_dates: int,
    **_:         Any,
) -> PolicyVerdict:
    """Banded SHEET_IS_PLI with horizontal date strips → horizontal stage axis."""
    fits = pli_axis == "sheet" and horiz_dates >= _DATE_STRIPS_FOR_SHEET_STAGE
    score = _BOOST if (candidate == "horizontal" and fits) else 0.0
    return PolicyVerdict(
        name="prefer_horizontal_when_sheet_with_horiz_date_strips",
        candidate=candidate,
        score_delta=score,
        message=f"pli={pli_axis} horiz_dates={horiz_dates}" if score else "",
    )


def prefer_vertical_when_sheet_with_vert_date_strips(
    candidate: str,
    *,
    pli_axis:   str,
    vert_dates: int,
    **_:        Any,
) -> PolicyVerdict:
    """SHEET_IS_PLI with vertical date strips → vertical stage axis."""
    fits = pli_axis == "sheet" and vert_dates >= _DATE_STRIPS_FOR_SHEET_STAGE
    score = _BOOST if (candidate == "vertical" and fits) else 0.0
    return PolicyVerdict(
        name="prefer_vertical_when_sheet_with_vert_date_strips",
        candidate=candidate,
        score_delta=score,
        message=f"pli={pli_axis} vert_dates={vert_dates}" if score else "",
    )


def prefer_horizontal_when_tabular_with_vert_date_strips(
    candidate: str,
    *,
    pli_axis:   str,
    vert_dates: int,
    **_:        Any,
) -> PolicyVerdict:
    """Tabular (vertical/sectional) with vertical date strips → horizontal stage axis
    (stage columns, apply_plan walks right per PLI row)."""
    fits = pli_axis in ("vertical", "sectional") and vert_dates >= _DATE_STRIPS_FOR_TABULAR_STAGE
    score = _BOOST if (candidate == "horizontal" and fits) else 0.0
    return PolicyVerdict(
        name="prefer_horizontal_when_tabular_with_vert_date_strips",
        candidate=candidate,
        score_delta=score,
        message=f"pli={pli_axis} vert_dates={vert_dates}" if score else "",
    )


def prefer_vertical_when_tabular_with_horiz_date_strips(
    candidate: str,
    *,
    pli_axis:    str,
    horiz_dates: int,
    **_:         Any,
) -> PolicyVerdict:
    """Tabular with horizontal date strips → vertical stage axis."""
    fits = pli_axis in ("vertical", "sectional") and horiz_dates >= _DATE_STRIPS_FOR_TABULAR_STAGE
    score = _BOOST if (candidate == "vertical" and fits) else 0.0
    return PolicyVerdict(
        name="prefer_vertical_when_tabular_with_horiz_date_strips",
        candidate=candidate,
        score_delta=score,
        message=f"pli={pli_axis} horiz_dates={horiz_dates}" if score else "",
    )
