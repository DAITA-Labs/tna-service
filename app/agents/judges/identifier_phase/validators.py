"""IdentifierPhaseJudge semantic validators.

Pydantic enforces the per-decision shape (decision/confidence literals,
non-empty reason). This module enforces:

  - decision == "rewrite" ⇒ alternative_coord must be set
  - decision in {"keep","drop"} ⇒ alternative_coord must be None
  - `finding_index` values must be unique across decisions (the phase
    judge must speak at most once per finding)
"""
from __future__ import annotations

from typing import Any

from app.agents._base import OutputVerdict
from app.agents.judges.identifier_phase.schema import IdentifierPhaseVerdict


def validate_identifier_phase_verdict(
    output: IdentifierPhaseVerdict,
    ctx: Any,
) -> OutputVerdict:
    """Reject phase verdicts that violate the cross-field invariants."""
    seen_indices: set[int] = set()
    for d in output.decisions:
        if d.finding_index in seen_indices:
            return OutputVerdict.retry(
                reason=(
                    f"finding_index={d.finding_index} appears in more than one "
                    f"decision; each finding must get at most one phase-level call"
                ),
            )
        seen_indices.add(d.finding_index)

        if d.decision == "rewrite" and d.alternative_coord is None:
            return OutputVerdict.retry(
                reason=(
                    f"decision='rewrite' on finding_index={d.finding_index} "
                    f"requires alternative_coord to be set"
                ),
            )
        if d.decision in ("keep", "drop") and d.alternative_coord is not None:
            return OutputVerdict.retry(
                reason=(
                    f"decision='{d.decision}' on finding_index={d.finding_index} "
                    f"must not carry alternative_coord"
                ),
            )
    return OutputVerdict.ok()
