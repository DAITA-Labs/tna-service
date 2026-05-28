"""StageFindingJudge semantic validators.

Pydantic enforces shape (decision/confidence literals, non-empty
reason). This module enforces the cross-field invariant Pydantic
alone cannot — and ALSO enforces that any `alternative_canonical`
the judge proposes is a real catalog entry, not a hallucination.

Without the catalog check the judge could rename a stage to
"sample_inspection_3" or any other fabricated string; downstream
consumers would then index into STAGE_SPECS expecting a real entry
and crash.
"""
from __future__ import annotations

from typing import Any

from app.agents._base import OutputVerdict
from app.agents.judges.stage_finding.schema import StageVerdict
from app.specs.stages import STAGE_CANONICALS


def validate_stage_verdict(output: StageVerdict, ctx: Any) -> OutputVerdict:
    """Reject verdicts where alternative_canonical contradicts decision or isn't catalogued."""
    if output.decision == "rewrite":
        if output.alternative_canonical is None:
            return OutputVerdict.retry(
                reason="decision='rewrite' requires alternative_canonical to be set",
            )
        if output.alternative_canonical not in STAGE_CANONICALS:
            return OutputVerdict.retry(
                reason=(
                    f"alternative_canonical {output.alternative_canonical!r} is not in "
                    f"STAGE_SPECS; choose one of {sorted(STAGE_CANONICALS)}"
                ),
            )
        return OutputVerdict.ok()

    if output.alternative_canonical is not None:
        return OutputVerdict.retry(
            reason=(
                f"decision='{output.decision}' must not carry alternative_canonical; "
                f"only 'rewrite' may supply one"
            ),
        )
    return OutputVerdict.ok()
