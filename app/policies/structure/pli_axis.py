"""PLI-axis policies — score each axis option from canvas + bag signals.

Each policy boosts the candidate string it favors based on the
structural signals passed in `policy_context`. The PliAxisPicker
composes them and picks the highest-scoring axis.

Candidate vocabulary matches the strings the legacy `_decide_pli_axis`
returned and that `LayoutAxes.pli_axis` already consumes: "sheet",
"sectional", "vertical", "horizontal".
"""
from __future__ import annotations

from typing import Any

from app.policies._base import PolicyVerdict


# Thresholds — mirror the constants from axis_inferrer.py exactly.
_KV_BLOCKS_FOR_SHEET            = 3
_DATA_ROWS_MAX_FOR_SHEET        = 5
_SHEET_SIZE_MAX                 = 600
_REPEATING_GROUPS_FOR_SECTIONAL = 3
_DATA_ROWS_MIN_FOR_SECTIONAL    = 10
_AXIS_RATIO                     = 2.0

_BOOST = 1.0


def prefer_sheet_for_kv_blocks(
    candidate: str,
    *,
    kv_count:    int,
    n_data_rows: int,
    sheet_size:  int,
    **_:         Any,
) -> PolicyVerdict:
    """Boost 'sheet' when many kv blocks and few data rows on a small sheet."""
    fits = (
        kv_count >= _KV_BLOCKS_FOR_SHEET
        and n_data_rows < _DATA_ROWS_MAX_FOR_SHEET
        and sheet_size < _SHEET_SIZE_MAX
    )
    score = _BOOST if (candidate == "sheet" and fits) else 0.0
    return PolicyVerdict(
        name="prefer_sheet_for_kv_blocks",
        candidate=candidate,
        score_delta=score,
        message=f"kv={kv_count} rows={n_data_rows} size={sheet_size}" if score else "",
    )


def prefer_sectional_for_repeating_groups(
    candidate: str,
    *,
    repeating_count: int,
    n_data_rows:     int,
    **_:             Any,
) -> PolicyVerdict:
    """Boost 'sectional' when ≥3 repeating row groups span ≥10 data rows."""
    fits = (
        repeating_count >= _REPEATING_GROUPS_FOR_SECTIONAL
        and n_data_rows >= _DATA_ROWS_MIN_FOR_SECTIONAL
    )
    score = _BOOST if (candidate == "sectional" and fits) else 0.0
    return PolicyVerdict(
        name="prefer_sectional_for_repeating_groups",
        candidate=candidate,
        score_delta=score,
        message=f"repeating={repeating_count} rows={n_data_rows}" if score else "",
    )


def prefer_vertical_when_more_rows_than_cols(
    candidate: str,
    *,
    n_data_rows: int,
    n_data_cols: int,
    **_:         Any,
) -> PolicyVerdict:
    """Boost 'vertical' when data rows outnumber data cols by ≥2×."""
    fits = n_data_rows > n_data_cols * _AXIS_RATIO
    score = _BOOST if (candidate == "vertical" and fits) else 0.0
    return PolicyVerdict(
        name="prefer_vertical_when_more_rows_than_cols",
        candidate=candidate,
        score_delta=score,
        message=f"rows={n_data_rows} cols={n_data_cols}" if score else "",
    )


def prefer_horizontal_when_more_cols_than_rows(
    candidate: str,
    *,
    n_data_rows: int,
    n_data_cols: int,
    **_:         Any,
) -> PolicyVerdict:
    """Boost 'horizontal' (transposed) when data cols outnumber rows by ≥2×."""
    fits = n_data_cols > n_data_rows * _AXIS_RATIO
    score = _BOOST if (candidate == "horizontal" and fits) else 0.0
    return PolicyVerdict(
        name="prefer_horizontal_when_more_cols_than_rows",
        candidate=candidate,
        score_delta=score,
        message=f"rows={n_data_rows} cols={n_data_cols}" if score else "",
    )
