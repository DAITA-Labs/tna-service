"""PlanCrossFieldPicker — aggregator over cross-field policies."""
from __future__ import annotations

from app.artifacts.finding import ValidationWarning
from app.artifacts.plan import LocationCandidate
from app.components.pickers.plan_cross_field import PlanCrossFieldPicker
from app.enums.field_location_mode import FieldLocationMode
from app.policies._base import PolicyVerdict


def _col_entry(col: int, score: float, eliminated: bool = False):
    return (
        LocationCandidate(mode=FieldLocationMode.COLUMN, column=col),
        score,
        eliminated,
    )


def test_review_runs_default_policies_in_order() -> None:
    """Default policies fire in registration order; verdicts/warnings concatenate."""
    picker = PlanCrossFieldPicker()
    scoreboard = {
        "io_number":     [],
        "quantity":      [],
        "ex_fty_date":   [],
        "shipment_date": [],
        "delivery_date": [],
    }
    verdicts, warnings = picker.review(scoreboard)

    # Both default policies should have fired
    names = {v.name for v in verdicts}
    assert "at_least_one_date_trio_member_present" in names
    assert "mandatory_canonicals_must_be_located"   in names

    # Two error warnings: date_trio_all_missing + two missing mandatories
    warning_names = {w.name for w in warnings}
    assert "date_trio_all_missing"           in warning_names
    assert "mandatory_missing_io_number"     in warning_names
    assert "mandatory_missing_quantity"      in warning_names


def test_review_with_clean_scoreboard_yields_no_warnings() -> None:
    picker = PlanCrossFieldPicker()
    scoreboard = {
        "io_number":     [_col_entry(1, 0.9)],
        "quantity":      [_col_entry(2, 0.9)],
        "ex_fty_date":   [_col_entry(3, 0.9)],
        "shipment_date": [_col_entry(4, 0.9)],
        "delivery_date": [_col_entry(5, 0.9)],
    }
    verdicts, warnings = picker.review(scoreboard)
    assert warnings == []
    # All verdicts should be passing (score_delta == 0.0).
    for v in verdicts:
        assert v.score_delta == 0.0


def test_custom_policies_replace_defaults() -> None:
    """Passing `policies=[…]` overrides the default policy list."""
    def stub_policy(scoreboard, **_) -> tuple[list, list]:
        return (
            [PolicyVerdict(name="stub", candidate="<plan>", score_delta=0.0)],
            [ValidationWarning(name="stub_warn", severity="info", message="ok")],
        )

    picker = PlanCrossFieldPicker(policies=[stub_policy])
    verdicts, warnings = picker.review({})
    assert len(verdicts) == 1
    assert verdicts[0].name == "stub"
    assert warnings[0].name == "stub_warn"


def test_empty_policy_list_yields_empty_output() -> None:
    picker = PlanCrossFieldPicker(policies=[])
    verdicts, warnings = picker.review({})
    assert verdicts == []
    assert warnings == []


def test_review_accepts_extra_kwargs_for_policies() -> None:
    """Policy kwargs propagate through `review`."""
    received: dict = {}

    def capturing_policy(scoreboard, **kwargs) -> tuple[list, list]:
        received.update(kwargs)
        return ([], [])

    picker = PlanCrossFieldPicker(policies=[capturing_policy])
    picker.review({}, score_floor=0.7, custom_arg="hello")
    assert received["score_floor"] == 0.7
    assert received["custom_arg"]  == "hello"
