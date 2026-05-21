"""PlanReviewer validator unit tests — the spec's anti-pattern guardrail."""
from __future__ import annotations

from types import SimpleNamespace

from app.agents.plan_reviewer.schema import PlanVerdict
from app.agents.plan_reviewer.validators import validate_plan_verdict


def _ctx(rows: list[int] | None = None) -> object:
    return SimpleNamespace(plan_rows=rows)


# ---------------------------------------------------------------------------
# happy paths
# ---------------------------------------------------------------------------

def test_all_defaults_ok() -> None:
    out = PlanVerdict()
    assert validate_plan_verdict(out, ctx=None).is_ok


def test_looks_correct_verdict_ok() -> None:
    out = PlanVerdict(verdict="looks_correct")
    assert validate_plan_verdict(out, ctx=None).is_ok


def test_needs_fix_verdict_ok() -> None:
    out = PlanVerdict(verdict="needs_fix")
    assert validate_plan_verdict(out, ctx=None).is_ok


def test_valid_correction_with_known_row_ok() -> None:
    out = PlanVerdict(
        verdict="needs_fix",
        row_corrections=[{"row": 2, "suggested_role": "anchor", "reason": "merged"}],
    )
    assert validate_plan_verdict(out, ctx=_ctx([1, 2, 3])).is_ok


def test_correction_without_suggested_role_ok() -> None:
    out = PlanVerdict(
        row_corrections=[{"row": 2, "reason": "suspicious"}],
    )
    assert validate_plan_verdict(out, ctx=_ctx([1, 2, 3])).is_ok


# ---------------------------------------------------------------------------
# rejection paths — verdict / confidence
# ---------------------------------------------------------------------------

def test_unknown_verdict_triggers_retry() -> None:
    out = PlanVerdict(verdict="yes")
    result = validate_plan_verdict(out, ctx=None)
    assert result.is_retry
    assert "yes" in result.reason


def test_confidence_above_one_triggers_retry() -> None:
    out = PlanVerdict(confidence=1.1)
    result = validate_plan_verdict(out, ctx=None)
    assert result.is_retry
    assert "1.1" in result.reason


def test_confidence_below_zero_triggers_retry() -> None:
    out = PlanVerdict(confidence=-0.1)
    result = validate_plan_verdict(out, ctx=None)
    assert result.is_retry


# ---------------------------------------------------------------------------
# rejection paths — row_corrections count
# ---------------------------------------------------------------------------

def test_six_corrections_triggers_retry() -> None:
    corrections = [{"row": i, "reason": "r"} for i in range(1, 7)]
    out = PlanVerdict(row_corrections=corrections)
    result = validate_plan_verdict(out, ctx=None)
    assert result.is_retry
    assert "6" in result.reason


def test_five_corrections_ok() -> None:
    corrections = [{"row": i, "reason": "r"} for i in range(1, 6)]
    out = PlanVerdict(row_corrections=corrections)
    assert validate_plan_verdict(out, ctx=None).is_ok


# ---------------------------------------------------------------------------
# rejection paths — identity_column_suggestion
# ---------------------------------------------------------------------------

def test_lowercase_column_letter_triggers_retry() -> None:
    out = PlanVerdict(identity_column_suggestion="b")
    result = validate_plan_verdict(out, ctx=None)
    assert result.is_retry
    assert "b" in result.reason


def test_column_with_digit_triggers_retry() -> None:
    out = PlanVerdict(identity_column_suggestion="B2")
    result = validate_plan_verdict(out, ctx=None)
    assert result.is_retry
    assert "B2" in result.reason


# ---------------------------------------------------------------------------
# rejection paths — row_corrections content
# ---------------------------------------------------------------------------

def test_non_int_row_triggers_retry() -> None:
    out = PlanVerdict(row_corrections=[{"row": "five", "reason": "bad"}])
    result = validate_plan_verdict(out, ctx=None)
    assert result.is_retry
    assert "not an int" in result.reason


def test_row_not_in_plan_rows_triggers_retry() -> None:
    out = PlanVerdict(row_corrections=[{"row": 99, "reason": "outside plan"}])
    result = validate_plan_verdict(out, ctx=_ctx([1, 2, 3]))
    assert result.is_retry
    assert "99" in result.reason


def test_invalid_suggested_role_triggers_retry() -> None:
    out = PlanVerdict(
        row_corrections=[{"row": 2, "suggested_role": "banana", "reason": "test"}],
    )
    result = validate_plan_verdict(out, ctx=_ctx([1, 2, 3]))
    assert result.is_retry
    assert "banana" in result.reason
