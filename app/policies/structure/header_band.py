"""Header-band policies — score and filter row candidates for the header anchor.

Each policy takes a row index plus a canvas keyword and returns one
`PolicyVerdict`. The HeaderBandPicker composes them.
"""
from __future__ import annotations

from typing import Any

from app.artifacts.canvas import GridCanvas
from app.policies._base import PolicyVerdict
from app.tools.canvas.query import aggregate_by_row, query_all


_DEFAULT_PHASE_WEIGHTS: dict[str, float] = {
    "identifier": 2.0,
    "stage":      1.0,
    "subfield":   0.5,
    "metadata":   1.0,
}


def prefer_spec_label_hits(
    row:           int,
    *,
    canvas:        GridCanvas,
    phase_weights: dict[str, float] | None = None,
    **_:           Any,
) -> PolicyVerdict:
    """Score this row by phase-weighted spec-alias matches across its cells.

    Identifier-phase hits are weighted highest because the identifier
    header is the typical anchor of a tabular layout (see
    `find_header_rows_via_specs` in `app/tools/canvas/query.py`).
    """
    weights = phase_weights or _DEFAULT_PHASE_WEIGHTS
    matches = query_all(canvas, restrict_rows={row})
    per_row = aggregate_by_row(matches)
    info    = per_row.get(row, {"phases": {}})
    score   = sum(
        weights.get(phase, 1.0) * count for phase, count in info["phases"].items()
    )
    return PolicyVerdict(
        name="prefer_spec_label_hits",
        candidate=row,
        score_delta=score,
        message=f"phase hits: {dict(info['phases'])}" if info["phases"] else "no matches",
    )


def eliminate_empty_rows(
    row:    int,
    *,
    canvas: GridCanvas,
    **_:    Any,
) -> PolicyVerdict:
    """Disqualify rows the canvas marked empty — they can never be headers."""
    matrix = canvas.channels.get("empty_row")
    is_empty = bool(matrix) and matrix[row - 1][0] == 1
    return PolicyVerdict(
        name="eliminate_empty_rows",
        candidate=row,
        score_delta=0.0,
        eliminate=is_empty,
        message="row marked empty" if is_empty else "",
    )
