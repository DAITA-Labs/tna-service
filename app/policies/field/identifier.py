"""Identifier policies — score candidates against a FieldSpec.

Two policy families coexist:

  * `score_column_via_spec(candidate: int, …)` — column-only, consumed by
    the legacy `IdentifierColumnPicker` and the 11 per-canonical extractors.
  * `score_lc_*` family — `LocationCandidate`-aware, mode-gated, consumed
    by the unified `IdentifierPicker`. Each variant short-circuits with
    `score_delta = 0.0` for candidates of the wrong mode, so the same
    policy list scores COLUMN, ROW, and KV_BLOCK candidates in one pass.
"""
from __future__ import annotations

from typing import Any

from app.artifacts.canvas import GridCanvas
from app.artifacts.plan import LocationCandidate
from app.enums.field_location_mode import FieldLocationMode
from app.policies._base import PolicyVerdict
from app.tools._registry import TOOL_REGISTRY


# ── Legacy column-only policy (IdentifierColumnPicker) ─────────────────────


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


# ── LocationCandidate-aware policies (IdentifierPicker, mode-gated) ────────


_KV_EXACT_MATCH_BOOST: float = 0.9


def score_lc_column_via_spec(
    candidate: LocationCandidate,
    *,
    canvas:    GridCanvas,
    rows:      list[int],
    spec:      Any,
    strips:    list,
    **_:       Any,
) -> PolicyVerdict:
    """Score a COLUMN-mode `LocationCandidate` via the column-scoring tool.

    Short-circuits to 0.0 for non-COLUMN candidates so the same policy
    list can score every mode in one pass.
    """
    if candidate.mode != FieldLocationMode.COLUMN or candidate.column is None:
        return PolicyVerdict(
            name="score_lc_column_via_spec",
            candidate=candidate,
            score_delta=0.0,
        )
    score = TOOL_REGISTRY["score_column_for_canonical"](
        canvas, candidate.column, rows, spec, strips,
    )
    return PolicyVerdict(
        name="score_lc_column_via_spec",
        candidate=candidate,
        score_delta=score,
        message=f"col={candidate.column} score={score:.2f}",
    )


def score_lc_row_via_spec(
    candidate: LocationCandidate,
    *,
    canvas:    GridCanvas,
    cols:      list[int],
    spec:      Any,
    strips:    list,
    **_:       Any,
) -> PolicyVerdict:
    """Score a ROW-mode `LocationCandidate`.

    Stub today: emits 0.0 so ROW candidates remain in the scoreboard
    for judge introspection but don't yet contribute score. A real
    row-scoring tool (transposed counterpart of `score_column_for_canonical`)
    lands in a follow-up.
    """
    if candidate.mode != FieldLocationMode.ROW or candidate.row is None:
        return PolicyVerdict(
            name="score_lc_row_via_spec",
            candidate=candidate,
            score_delta=0.0,
        )
    return PolicyVerdict(
        name="score_lc_row_via_spec",
        candidate=candidate,
        score_delta=0.0,
        message="row-mode scoring stub",
    )


def score_lc_kv_via_label_match(
    candidate: LocationCandidate,
    *,
    spec:      Any,
    **_:       Any,
) -> PolicyVerdict:
    """Score a KV_BLOCK candidate by exact label match against the spec's aliases.

    Exact case-insensitive alias match → `_KV_EXACT_MATCH_BOOST`. Fuzzy
    matching (rapidfuzz) is a future policy. Non-KV candidates score 0.
    """
    if candidate.mode != FieldLocationMode.KV_BLOCK or candidate.kv_block is None:
        return PolicyVerdict(
            name="score_lc_kv_via_label_match",
            candidate=candidate,
            score_delta=0.0,
        )
    label_lower = (candidate.kv_block.label_text or "").strip().lower()
    if not label_lower:
        return PolicyVerdict(
            name="score_lc_kv_via_label_match",
            candidate=candidate,
            score_delta=0.0,
            message="empty label",
        )
    aliases_lower = {a.lower() for a in spec.aliases}
    if label_lower in aliases_lower:
        return PolicyVerdict(
            name="score_lc_kv_via_label_match",
            candidate=candidate,
            score_delta=_KV_EXACT_MATCH_BOOST,
            message=f"alias match: {label_lower}",
        )
    return PolicyVerdict(
        name="score_lc_kv_via_label_match",
        candidate=candidate,
        score_delta=0.0,
        message=f"no alias match for: {label_lower}",
    )
