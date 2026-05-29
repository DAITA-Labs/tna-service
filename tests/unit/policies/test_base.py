"""PolicyVerdict + aggregate_verdicts coverage."""
from __future__ import annotations

import dataclasses

import pytest

from app.policies import PolicyVerdict, aggregate_verdicts


def test_policy_verdict_is_frozen() -> None:
    v = PolicyVerdict(name="boost", candidate=1, score_delta=0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.score_delta = 1.0  # type: ignore[misc]


def test_policy_verdict_defaults() -> None:
    v = PolicyVerdict(name="boost", candidate="row-3")
    assert v.score_delta == 0.0
    assert v.eliminate is False
    assert v.message == ""


def test_aggregate_empty_returns_zero_and_not_eliminated() -> None:
    total, eliminated = aggregate_verdicts([])
    assert total == 0.0
    assert eliminated is False


def test_aggregate_sums_score_deltas() -> None:
    verdicts = [
        PolicyVerdict("a", 1, 0.5),
        PolicyVerdict("b", 1, 0.3),
        PolicyVerdict("c", 1, -0.1),
    ]
    total, eliminated = aggregate_verdicts(verdicts)
    assert total == pytest.approx(0.7)
    assert eliminated is False


def test_aggregate_eliminates_if_any_policy_eliminates() -> None:
    verdicts = [
        PolicyVerdict("a", 1, 0.5),
        PolicyVerdict("b", 1, 0.0, eliminate=True),
        PolicyVerdict("c", 1, 0.3),
    ]
    total, eliminated = aggregate_verdicts(verdicts)
    assert eliminated is True
    # Score is still summed — callers may want to see why the candidate
    # would have scored well even though it was killed.
    assert total == pytest.approx(0.8)
