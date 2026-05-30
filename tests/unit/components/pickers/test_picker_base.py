"""Picker base — candidate-loop behaviour with synthetic policies + stub subclass."""
from __future__ import annotations

from typing import Any, Sequence

from app.components.pickers._base import Picker
from app.policies import PolicyVerdict


# ── Stub subclass — provides candidates() so the base's run() pieces work. ──


class _IntPicker(Picker[int]):
    """A trivial Picker subclass that returns whatever `_candidates` was given."""

    def __init__(self, policies, candidates_list, score_floor: float = 0.0) -> None:
        super().__init__(policies=policies, score_floor=score_floor)
        self._candidates_list = list(candidates_list)

    def candidates(self, **_: Any) -> Sequence[int]:
        return self._candidates_list


# ── Synthetic policies. ────────────────────────────────────────────────────


def _boost_if_even(candidate: int, **_: Any) -> PolicyVerdict:
    return PolicyVerdict(
        name="boost_if_even",
        candidate=candidate,
        score_delta=1.0 if candidate % 2 == 0 else 0.0,
    )


def _penalise_negatives(candidate: int, **_: Any) -> PolicyVerdict:
    return PolicyVerdict(
        name="penalise_negatives",
        candidate=candidate,
        score_delta=-0.5 if candidate < 0 else 0.0,
    )


def _eliminate_if_zero(candidate: int, **_: Any) -> PolicyVerdict:
    return PolicyVerdict(
        name="eliminate_if_zero",
        candidate=candidate,
        score_delta=0.0,
        eliminate=(candidate == 0),
    )


# ── Tests. ─────────────────────────────────────────────────────────────────


def test_score_candidates_returns_top_scoring_survivor() -> None:
    picker = _IntPicker(policies=[_boost_if_even], candidates_list=[1, 2, 3, 4])
    winner, verdicts = picker._score_candidates(picker.candidates())
    assert winner in {2, 4}  # both score 1.0; tie-break unspecified
    assert len(verdicts) == 4


def test_eliminated_candidate_never_wins() -> None:
    picker = _IntPicker(
        policies=[_boost_if_even, _eliminate_if_zero],
        candidates_list=[0, 1, 2],
    )
    winner, _ = picker._score_candidates(picker.candidates())
    # 0 → eliminated even though +0.0 from boost; 1 → 0.0; 2 → 1.0
    assert winner == 2


def test_returns_none_when_all_candidates_eliminated() -> None:
    picker = _IntPicker(
        policies=[_eliminate_if_zero],
        candidates_list=[0],
    )
    winner, verdicts = picker._score_candidates(picker.candidates())
    assert winner is None
    # The verdict trail still records the eliminated candidate.
    assert len(verdicts) == 1
    assert verdicts[0].eliminate is True


def test_returns_none_when_top_score_below_floor() -> None:
    picker = _IntPicker(
        policies=[_boost_if_even],
        candidates_list=[1, 3, 5],   # all odd → all score 0.0
        score_floor=0.5,
    )
    winner, _ = picker._score_candidates(picker.candidates())
    assert winner is None


def test_returns_winner_when_top_score_meets_floor() -> None:
    picker = _IntPicker(
        policies=[_boost_if_even],
        candidates_list=[1, 2, 3],   # 2 scores 1.0
        score_floor=0.5,
    )
    winner, _ = picker._score_candidates(picker.candidates())
    assert winner == 2


def test_verdict_trail_contains_every_policy_for_every_candidate() -> None:
    picker = _IntPicker(
        policies=[_boost_if_even, _penalise_negatives, _eliminate_if_zero],
        candidates_list=[-1, 0, 1, 2],
    )
    _, verdicts = picker._score_candidates(picker.candidates())
    assert len(verdicts) == 4 * 3  # candidates × policies
    names = {v.name for v in verdicts}
    assert names == {"boost_if_even", "penalise_negatives", "eliminate_if_zero"}


def test_picker_with_no_policies_returns_no_winner() -> None:
    picker = _IntPicker(policies=[], candidates_list=[1, 2, 3])
    winner, verdicts = picker._score_candidates(picker.candidates())
    # No policies → no score deltas → all candidates tie at 0.0; the
    # default score_floor=0.0 admits them. max() returns the first.
    assert winner == 1
    assert verdicts == []


def test_picker_with_no_candidates_returns_none() -> None:
    picker = _IntPicker(policies=[_boost_if_even], candidates_list=[])
    winner, verdicts = picker._score_candidates(picker.candidates())
    assert winner is None
    assert verdicts == []


def test_candidates_raises_when_subclass_does_not_override() -> None:
    """The base's `candidates()` is a NotImplementedError stub."""
    import pytest
    raw = Picker[int]()
    with pytest.raises(NotImplementedError):
        raw.candidates()


def test_negative_candidate_can_still_win_with_high_boost() -> None:
    """Policies compose additively — a positive boost can outweigh a penalty."""
    def big_boost(c: int, **_: Any) -> PolicyVerdict:
        return PolicyVerdict("big_boost", c, score_delta=10.0)

    picker = _IntPicker(
        policies=[big_boost, _penalise_negatives],
        candidates_list=[-1, 1],
    )
    winner, _ = picker._score_candidates(picker.candidates())
    # -1 scores 10.0 - 0.5 = 9.5; 1 scores 10.0 + 0.0 = 10.0. 1 wins.
    assert winner == 1


# ── score_all() — public scoreboard accessor ───────────────────────────────


def test_score_all_returns_every_candidate_with_aggregate_score() -> None:
    picker = _IntPicker(
        policies=[_boost_if_even, _penalise_negatives],
        candidates_list=[-2, -1, 0, 1, 2],
    )
    scoreboard, verdicts = picker.score_all()

    assert len(scoreboard) == 5  # every candidate present (no winner-only filter)
    by_candidate = {c: (score, elim) for c, score, elim in scoreboard}
    assert by_candidate[-2] == (1.0 - 0.5, False)     # boost(even) + penalty
    assert by_candidate[-1] == (0.0 - 0.5, False)     # only penalty
    assert by_candidate[0]  == (1.0,        False)    # boost only
    assert by_candidate[1]  == (0.0,        False)
    assert by_candidate[2]  == (1.0,        False)
    assert len(verdicts) == 5 * 2  # candidates × policies


def test_score_all_preserves_eliminated_candidates_with_flag() -> None:
    picker = _IntPicker(
        policies=[_boost_if_even, _eliminate_if_zero],
        candidates_list=[0, 1, 2],
    )
    scoreboard, _ = picker.score_all()

    by_candidate = {c: (score, elim) for c, score, elim in scoreboard}
    assert by_candidate[0] == (1.0, True)    # eliminated but score retained
    assert by_candidate[1] == (0.0, False)
    assert by_candidate[2] == (1.0, False)


def test_score_all_preserves_candidate_order() -> None:
    picker = _IntPicker(
        policies=[_boost_if_even],
        candidates_list=[5, 2, 7, 4, 1],
    )
    scoreboard, _ = picker.score_all()
    assert [c for c, _, _ in scoreboard] == [5, 2, 7, 4, 1]


def test_score_all_and_score_candidates_agree_on_winner() -> None:
    """Whatever score_all reports, _score_candidates picks the same winner."""
    picker = _IntPicker(
        policies=[_boost_if_even, _penalise_negatives],
        candidates_list=[-2, 1, 2, 4],
    )
    scoreboard, _ = picker.score_all()
    winner, _   = picker._score_candidates(picker.candidates())

    surviving = [(c, score) for c, score, elim in scoreboard if not elim]
    expected_winner, _ = max(surviving, key=lambda pair: pair[1])
    assert winner == expected_winner


def test_score_all_empty_candidates_returns_empty_scoreboard() -> None:
    picker = _IntPicker(policies=[_boost_if_even], candidates_list=[])
    scoreboard, verdicts = picker.score_all()
    assert scoreboard == []
    assert verdicts == []


def test_score_all_no_policies_returns_zero_scores() -> None:
    picker = _IntPicker(policies=[], candidates_list=[1, 2, 3])
    scoreboard, verdicts = picker.score_all()
    assert [(c, s, e) for c, s, e in scoreboard] == [(1, 0.0, False), (2, 0.0, False), (3, 0.0, False)]
    assert verdicts == []
