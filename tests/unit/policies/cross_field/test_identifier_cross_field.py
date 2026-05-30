"""Cross-field identifier policies — plan-level checks over the scoreboard."""
from __future__ import annotations

from app.artifacts.plan import LocationCandidate
from app.enums.field_location_mode import FieldLocationMode
from app.policies.cross_field.identifier import (
    at_least_one_date_trio_member_present,
    mandatory_canonicals_must_be_located,
)


def _col_entry(col: int, score: float, eliminated: bool = False):
    return (
        LocationCandidate(mode=FieldLocationMode.COLUMN, column=col),
        score,
        eliminated,
    )


# ── at_least_one_date_trio_member_present ──────────────────────────────────


def test_all_three_dates_missing_emits_error_warning() -> None:
    scoreboard = {
        "ex_fty_date":   [],
        "shipment_date": [],
        "delivery_date": [],
    }
    verdicts, warnings = at_least_one_date_trio_member_present(scoreboard)
    assert len(verdicts) == 1
    assert verdicts[0].score_delta == -1.0
    assert len(warnings) == 1
    assert warnings[0].name == "date_trio_all_missing"
    assert warnings[0].severity == "error"


def test_all_three_dates_below_floor_emits_error_warning() -> None:
    scoreboard = {
        "ex_fty_date":   [_col_entry(1, 0.3)],
        "shipment_date": [_col_entry(2, 0.2)],
        "delivery_date": [_col_entry(3, 0.4)],
    }
    verdicts, warnings = at_least_one_date_trio_member_present(scoreboard, score_floor=0.5)
    assert verdicts[0].score_delta == -1.0
    assert any(w.name == "date_trio_all_missing" for w in warnings)


def test_one_date_above_floor_no_warning() -> None:
    scoreboard = {
        "ex_fty_date":   [_col_entry(1, 0.9)],
        "shipment_date": [],
        "delivery_date": [],
    }
    verdicts, warnings = at_least_one_date_trio_member_present(scoreboard)
    assert verdicts[0].score_delta == 0.0
    assert warnings == []


def test_eliminated_candidates_dont_count_as_located() -> None:
    scoreboard = {
        "ex_fty_date":   [_col_entry(1, 0.9, eliminated=True)],
        "shipment_date": [],
        "delivery_date": [],
    }
    verdicts, warnings = at_least_one_date_trio_member_present(scoreboard)
    # The 0.9 candidate is eliminated → no member located → error
    assert verdicts[0].score_delta == -1.0
    assert any(w.name == "date_trio_all_missing" for w in warnings)


# ── mandatory_canonicals_must_be_located ───────────────────────────────────


def test_both_mandatory_located_above_floor_no_warning() -> None:
    scoreboard = {
        "io_number": [_col_entry(1, 0.9)],
        "quantity":  [_col_entry(2, 0.85)],
    }
    verdicts, warnings = mandatory_canonicals_must_be_located(scoreboard)
    # Two passing verdicts (one per mandatory canonical), no warnings
    assert len(verdicts) == 2
    for v in verdicts:
        assert v.score_delta == 0.0
    assert warnings == []


def test_mandatory_canonical_with_no_candidates_emits_error() -> None:
    scoreboard = {
        "io_number": [],
        "quantity":  [_col_entry(2, 0.9)],
    }
    verdicts, warnings = mandatory_canonicals_must_be_located(scoreboard)
    error_verdict = next(v for v in verdicts if v.candidate == "<plan:io_number>")
    assert error_verdict.score_delta == -1.0
    error_warning = next(w for w in warnings if w.name == "mandatory_missing_io_number")
    assert error_warning.severity == "error"


def test_mandatory_canonical_below_floor_emits_warning() -> None:
    scoreboard = {
        "io_number": [_col_entry(1, 0.3)],   # below 0.5 floor
        "quantity":  [_col_entry(2, 0.9)],
    }
    verdicts, warnings = mandatory_canonicals_must_be_located(scoreboard, score_floor=0.5)
    low_verdict = next(v for v in verdicts if v.candidate == "<plan:io_number>")
    assert low_verdict.score_delta == -0.5
    low_warning = next(w for w in warnings
                        if w.name == "mandatory_low_confidence_io_number")
    assert low_warning.severity == "warning"


def test_mandatory_canonicals_custom_set() -> None:
    """Caller can override the mandatory set."""
    scoreboard = {
        "style_code": [],
    }
    verdicts, warnings = mandatory_canonicals_must_be_located(
        scoreboard, mandatory=("style_code",), score_floor=0.5,
    )
    assert any(w.name == "mandatory_missing_style_code" for w in warnings)
    assert all(v.candidate.startswith("<plan:") for v in verdicts)


def test_mandatory_canonical_eliminated_treated_as_missing() -> None:
    scoreboard = {
        "io_number": [_col_entry(1, 0.9, eliminated=True)],
        "quantity":  [_col_entry(2, 0.9)],
    }
    verdicts, warnings = mandatory_canonicals_must_be_located(scoreboard)
    assert any(w.name == "mandatory_missing_io_number" for w in warnings)
