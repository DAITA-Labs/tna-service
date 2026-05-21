"""PlanReviewer semantic validators — the spec's anti-pattern guardrail."""
from __future__ import annotations

import re
from typing import Any

from app.agents._base import OutputVerdict
from app.agents.plan_reviewer.schema import PlanVerdict
from app.enums.row_role import RowRole


_VALID_VERDICTS = {"looks_correct", "needs_fix"}
_COL_LETTER_RE = re.compile(r"^[A-Z]+$")
_MAX_CORRECTIONS = 5


def validate_plan_verdict(output: PlanVerdict, ctx: Any) -> OutputVerdict:
    """Reject verdicts that reference non-existent rows, bad roles, or are malformed.

    `ctx` is expected to expose `.plan_rows: list[int]` — the indices of rows in
    the SheetPlan being reviewed. The Component wrapper attaches this attribute
    before invoking the agent so this validator can sanity-check corrections.
    """
    if output.verdict not in _VALID_VERDICTS:
        return OutputVerdict.retry(
            reason=f"verdict {output.verdict!r} is not one of {sorted(_VALID_VERDICTS)}",
        )
    if not 0.0 <= output.confidence <= 1.0:
        return OutputVerdict.retry(
            reason=f"confidence {output.confidence} is outside [0, 1]",
        )
    if len(output.row_corrections) > _MAX_CORRECTIONS:
        return OutputVerdict.retry(
            reason=f"row_corrections has {len(output.row_corrections)} entries; max is {_MAX_CORRECTIONS}",
        )
    if output.identity_column_suggestion is not None:
        if not _COL_LETTER_RE.match(output.identity_column_suggestion):
            return OutputVerdict.retry(
                reason=f"identity_column_suggestion {output.identity_column_suggestion!r} is not a valid Excel column letter",
            )

    known_rows = set(getattr(ctx, "plan_rows", []) or [])
    valid_roles = {role.value for role in RowRole}

    for i, correction in enumerate(output.row_corrections):
        row = correction.get("row")
        if not isinstance(row, int):
            return OutputVerdict.retry(
                reason=f"row_corrections[{i}].row {row!r} is not an int",
            )
        if known_rows and row not in known_rows:
            return OutputVerdict.retry(
                reason=f"row_corrections[{i}].row {row} is not in plan.rows",
            )
        suggested = correction.get("suggested_role")
        if suggested is not None and suggested not in valid_roles:
            return OutputVerdict.retry(
                reason=f"row_corrections[{i}].suggested_role {suggested!r} is not in {sorted(valid_roles)}",
            )

    return OutputVerdict.ok()
