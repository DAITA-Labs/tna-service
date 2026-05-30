"""PlanCrossFieldPicker — run cross-field policies over the global scoreboard.

Unlike the per-canonical pickers, this one doesn't operate on a single
candidate list — it inspects the WHOLE plan scoreboard and emits
plan-level verdicts + ValidationWarnings.

NOT a `Picker[C]` subclass: its inputs and outputs don't match the
candidate-loop shape (no winner to pick). NOT a Haystack `@component`:
used as an internal helper by `PlanAssembler` (planned).

Adding a new cross-field rule = one new policy function + one line in
this picker's `policies` list.
"""
from __future__ import annotations

from typing import Any, Callable

from app.artifacts.finding import ValidationWarning
from app.policies._base import PolicyVerdict
from app.policies.cross_field.identifier import (
    ScoreBoard,
    at_least_one_date_trio_member_present,
    mandatory_canonicals_must_be_located,
)


CrossFieldPolicy = Callable[..., tuple[list[PolicyVerdict], list[ValidationWarning]]]


_DEFAULT_POLICIES: tuple[CrossFieldPolicy, ...] = (
    at_least_one_date_trio_member_present,
    mandatory_canonicals_must_be_located,
)


class PlanCrossFieldPicker:
    """Run a list of cross-field policies over the plan scoreboard."""

    def __init__(self, policies: list[CrossFieldPolicy] | None = None) -> None:
        self.policies: list[CrossFieldPolicy] = (
            list(policies) if policies is not None else list(_DEFAULT_POLICIES)
        )

    def review(
        self,
        scoreboard:    ScoreBoard,
        **policy_kwargs: Any,
    ) -> tuple[list[PolicyVerdict], list[ValidationWarning]]:
        """Run every cross-field policy. Return aggregated (verdicts, warnings).

        Each policy reads the scoreboard and returns its own verdicts +
        warnings; this method concatenates them in policy order so the
        audit trail reflects the order policies were applied.
        """
        all_verdicts: list[PolicyVerdict]     = []
        all_warnings: list[ValidationWarning] = []
        for policy in self.policies:
            verdicts, warnings = policy(scoreboard, **policy_kwargs)
            all_verdicts.extend(verdicts)
            all_warnings.extend(warnings)
        return all_verdicts, all_warnings
