"""MetadataFindingJudge semantic validators.

Enforces the same cross-field invariant as the stage judge: `rewrite`
must carry an `alternative_canonical` and the value must come from
METADATA_CANONICALS. `keep` and `drop` must not carry one.
"""
from __future__ import annotations

from typing import Any

from app.agents._base import OutputVerdict
from app.agents.judges.metadata.schema import MetadataVerdict
from app.specs.metadata import METADATA_CANONICALS


def validate_metadata_verdict(output: MetadataVerdict, ctx: Any) -> OutputVerdict:
    """Reject verdicts where alternative_canonical contradicts decision or isn't catalogued."""
    if output.decision == "rewrite":
        if output.alternative_canonical is None:
            return OutputVerdict.retry(
                reason="decision='rewrite' requires alternative_canonical to be set",
            )
        if output.alternative_canonical not in METADATA_CANONICALS:
            return OutputVerdict.retry(
                reason=(
                    f"alternative_canonical {output.alternative_canonical!r} is not in "
                    f"METADATA_SPECS; choose one of {sorted(METADATA_CANONICALS)}"
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
