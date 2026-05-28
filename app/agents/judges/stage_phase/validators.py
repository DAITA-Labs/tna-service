"""StagePhaseJudge semantic validators.

Enforces:
  - decision == "rewrite" ⇒ alternative_canonical must be set AND
    must exist in STAGE_CANONICALS
  - decision in {"keep","drop"} ⇒ alternative_canonical must be None
  - Each (row, stage_index) pair speaks at most once across decisions
"""
from __future__ import annotations

from typing import Any

from app.agents._base import OutputVerdict
from app.agents.judges.stage_phase.schema import StagePhaseVerdict
from app.specs.stages import STAGE_CANONICALS


def validate_stage_phase_verdict(
    output: StagePhaseVerdict,
    ctx: Any,
) -> OutputVerdict:
    """Reject phase verdicts that violate the cross-decision invariants."""
    seen: set[tuple[int, int]] = set()
    for d in output.decisions:
        key = (d.row, d.stage_index)
        if key in seen:
            return OutputVerdict.retry(
                reason=(
                    f"(row={d.row}, stage_index={d.stage_index}) appears in more "
                    f"than one decision; each stage must get at most one phase-level call"
                ),
            )
        seen.add(key)

        if d.decision == "rewrite":
            if d.alternative_canonical is None:
                return OutputVerdict.retry(
                    reason=(
                        f"decision='rewrite' on (row={d.row}, stage_index={d.stage_index}) "
                        f"requires alternative_canonical to be set"
                    ),
                )
            if d.alternative_canonical not in STAGE_CANONICALS:
                return OutputVerdict.retry(
                    reason=(
                        f"alternative_canonical={d.alternative_canonical!r} on "
                        f"(row={d.row}, stage_index={d.stage_index}) is not in "
                        f"STAGE_SPECS; choose one of {sorted(STAGE_CANONICALS)}"
                    ),
                )
        elif d.alternative_canonical is not None:
            return OutputVerdict.retry(
                reason=(
                    f"decision='{d.decision}' on (row={d.row}, stage_index={d.stage_index}) "
                    f"must not carry alternative_canonical"
                ),
            )
    return OutputVerdict.ok()
