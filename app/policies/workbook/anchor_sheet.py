"""Anchor-sheet policies — score candidate sheets for serving as a cluster's anchor."""
from __future__ import annotations

from typing import Any

from app.artifacts.workbook import SheetSignature
from app.policies._base import PolicyVerdict


def prefer_richer_sheet(
    candidate: str,
    *,
    signatures_by_name: dict[str, SheetSignature],
    **_:                Any,
) -> PolicyVerdict:
    """Boost candidates by the size of their non-blank mask.

    The richest sheet usually carries the cleanest header row + the most
    data rows, so its structure-phase output transfers best to its
    siblings (matches the legacy `pick_anchor_sheet_name` rule).
    """
    sig = signatures_by_name.get(candidate)
    score = float(len(sig.non_blank_mask)) if sig is not None else 0.0
    return PolicyVerdict(
        name="prefer_richer_sheet",
        candidate=candidate,
        score_delta=score,
        message=f"non_blank_cells={int(score)}" if score else "",
    )
