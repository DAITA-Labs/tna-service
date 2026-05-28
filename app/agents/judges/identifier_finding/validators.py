"""IdentifierFindingJudge semantic validators.

The Pydantic schema enforces shape (decision in {keep,drop,rewrite},
non-empty reason, valid confidence literal). The semantic validator
below enforces the cross-field invariant Pydantic alone cannot:

  - decision == "rewrite"   ⇒ alternative_coord must be set
  - decision in {"keep","drop"} ⇒ alternative_coord must be None

A violation triggers an OutputVerdict.retry, which routes the verdict
back through the prompt with the failure reason appended.
"""
from __future__ import annotations

from typing import Any

from app.agents._base import OutputVerdict
from app.agents.judges.identifier_finding.schema import IdentifierVerdict


def validate_identifier_verdict(output: IdentifierVerdict, ctx: Any) -> OutputVerdict:
    """Reject verdicts whose alternative_coord doesn't agree with their decision."""
    if output.decision == "rewrite" and output.alternative_coord is None:
        return OutputVerdict.retry(
            reason="decision='rewrite' requires alternative_coord to be set",
        )
    if output.decision in ("keep", "drop") and output.alternative_coord is not None:
        return OutputVerdict.retry(
            reason=(
                f"decision='{output.decision}' must not carry alternative_coord; "
                f"only 'rewrite' may supply one"
            ),
        )
    return OutputVerdict.ok()
