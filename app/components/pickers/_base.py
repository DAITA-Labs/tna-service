"""Picker base — template-method `Component` for candidate-loop scoring.

Every concrete picker:
  - inherits `Picker`
  - sets `self.policies` in `__init__`
  - overrides `candidates(...)` to return its candidate list
  - overrides `run(...)` with a `@component.output_types(...)`-decorated
    signature that calls `self._score_candidates(...)`
  - applies Haystack's `@component` decorator at the class level

The base intentionally is NOT a Haystack `@component` — it has no `run`
signature suitable for the pipeline DSL, only the algorithm that
subclasses share. Haystack's `ComponentMeta` is incompatible with
`abc.ABC` (same note as `app/components/_base.py`); we use plain
`NotImplementedError` stubs instead.
"""
from __future__ import annotations

from typing import Any, Callable, Generic, Sequence, TypeVar

from app.components._base import Component
from app.policies._base import PolicyVerdict, aggregate_verdicts


C = TypeVar("C")

#: A policy is a callable that takes a candidate + arbitrary context kwargs
#: and returns one PolicyVerdict for that candidate.
Policy = Callable[..., PolicyVerdict]


class Picker(Component, Generic[C]):
    """Template-method base for layered candidate-loop pickers.

    `policies` is owned as instance state (set by subclasses in `__init__`)
    so individual picker instances can be reconfigured per pipeline tuning
    without rebuilding the class.

    `score_floor` is the minimum aggregate score a surviving candidate
    must clear to be returned as the winner. Default 0.0 means "any
    non-negative survivor wins"; subclasses raise this when the decision
    needs a confidence floor.
    """

    def __init__(
        self,
        policies:    list[Policy] | None = None,
        score_floor: float = 0.0,
    ) -> None:
        Component.__init__(self)
        self.policies:    list[Policy] = list(policies) if policies else []
        self.score_floor: float        = score_floor

    def candidates(self, **kwargs: Any) -> Sequence[C]:
        """Return the candidates this picker should rank. Subclasses MUST override."""
        raise NotImplementedError(
            f"{type(self).__name__} must override candidates()."
        )

    def _score_candidates(
        self,
        candidates:      Sequence[C],
        **policy_context: Any,
    ) -> tuple[C | None, list[PolicyVerdict]]:
        """Run every policy against every candidate; pick the top survivor.

        Returns `(winner, verdicts)` where:
          - `winner` is the highest-scoring non-eliminated candidate whose
            aggregate score clears `score_floor`, or `None` if no
            candidate qualifies.
          - `verdicts` is the full audit trail (every policy × every
            candidate, in order).

        Tie-breaking is unspecified — when two candidates share the top
        score, `max()`'s first-encountered-wins semantics apply.
        """
        all_verdicts: list[PolicyVerdict]            = []
        scored:       list[tuple[C, float, bool]]    = []

        for candidate in candidates:
            verdicts_for_candidate = [
                policy(candidate, **policy_context) for policy in self.policies
            ]
            all_verdicts.extend(verdicts_for_candidate)
            total, eliminated = aggregate_verdicts(verdicts_for_candidate)
            scored.append((candidate, total, eliminated))

        surviving = [(c, score) for c, score, elim in scored if not elim]
        if not surviving:
            return None, all_verdicts

        winner, top_score = max(surviving, key=lambda pair: pair[1])
        if top_score < self.score_floor:
            return None, all_verdicts
        return winner, all_verdicts
