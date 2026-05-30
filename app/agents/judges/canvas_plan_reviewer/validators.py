"""CanvasPlanReviewer semantic validators.

Pydantic enforces shape (decision literal, repick fields). The semantic
validator below enforces the cross-field invariants the schema can't:

  - decision == "repick"   ⇒ at least one repick entry
  - decision != "repick"   ⇒ repicks must be empty
  - each repick's mode must match the slot it carries:
      column   ↔ column   set, row + kv_label_coord cleared
      row      ↔ row      set, column + kv_label_coord cleared
      kv_block ↔ kv_label_coord set, column + row cleared

A violation triggers OutputVerdict.retry so the agent can self-correct.
"""
from __future__ import annotations

from typing import Any

from app.agents._base import OutputVerdict
from app.agents.judges.canvas_plan_reviewer.schema import (
    CanonicalRepick,
    PlanReviewVerdict,
)


def validate_plan_review_verdict(
    output: PlanReviewVerdict, ctx: Any,
) -> OutputVerdict:
    """Reject verdicts whose repick set disagrees with the decision."""
    if output.decision == "repick" and not output.repicks:
        return OutputVerdict.retry(
            reason="decision='repick' requires at least one repick entry",
        )
    if output.decision != "repick" and output.repicks:
        return OutputVerdict.retry(
            reason=(
                f"decision='{output.decision}' must not carry repicks; "
                f"only 'repick' may supply them"
            ),
        )
    for r in output.repicks:
        violation = _check_repick_mode_slots(r)
        if violation is not None:
            return OutputVerdict.retry(reason=violation)
    return OutputVerdict.ok()


def _check_repick_mode_slots(r: CanonicalRepick) -> str | None:
    """Return a violation message or None if the repick's slots match its mode."""
    if r.mode == "column":
        if r.column is None:
            return f"repick for '{r.canonical}' mode='column' requires column"
        if r.row is not None or r.kv_label_coord is not None:
            return (
                f"repick for '{r.canonical}' mode='column' must not carry "
                "row or kv_label_coord"
            )
    elif r.mode == "row":
        if r.row is None:
            return f"repick for '{r.canonical}' mode='row' requires row"
        if r.column is not None or r.kv_label_coord is not None:
            return (
                f"repick for '{r.canonical}' mode='row' must not carry "
                "column or kv_label_coord"
            )
    elif r.mode == "kv_block":
        if r.kv_label_coord is None:
            return (
                f"repick for '{r.canonical}' mode='kv_block' requires kv_label_coord"
            )
        if r.column is not None or r.row is not None:
            return (
                f"repick for '{r.canonical}' mode='kv_block' must not carry "
                "column or row"
            )
    return None
