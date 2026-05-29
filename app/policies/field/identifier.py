"""Identifier-column policies — score column candidates against a FieldSpec.

Single policy today: wrap the `score_column_for_canonical` tool so it
emits a `PolicyVerdict` consumable by `IdentifierColumnPicker`. New
column-scoring signals (e.g., strip-confirmation boost, anti-dedup
penalty) drop in as additional policies without touching the picker.
"""
from __future__ import annotations

from typing import Any

from app.artifacts.canvas import GridCanvas
from app.policies._base import PolicyVerdict
from app.tools._registry import TOOL_REGISTRY


def score_column_via_spec(
    candidate: int,
    *,
    canvas:    GridCanvas,
    rows:      list[int],
    spec:      Any,
    strips:    list,
    **_:       Any,
) -> PolicyVerdict:
    """Score a column by how well it matches the given canonical's FieldSpec.

    Delegates to the deterministic `score_column_for_canonical` tool,
    which combines strip overlap + per-cell dtype match + per-cell
    constraint pass rate into a single [0, 1] score.
    """
    score_fn = TOOL_REGISTRY["score_column_for_canonical"]
    score    = score_fn(canvas, candidate, rows, spec, strips)
    return PolicyVerdict(
        name="score_column_via_spec",
        candidate=candidate,
        score_delta=score,
        message=f"spec={spec.canonical} score={score:.2f}",
    )
