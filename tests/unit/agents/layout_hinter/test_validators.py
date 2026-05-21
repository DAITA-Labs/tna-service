"""LayoutHinter validator unit tests."""
from __future__ import annotations

from app.agents.layout_hinter.schema import LayoutHints
from app.agents.layout_hinter.validators import validate_layout_hints


# ---------------------------------------------------------------------------
# happy paths
# ---------------------------------------------------------------------------

def test_all_none_output_ok() -> None:
    out = LayoutHints()
    assert validate_layout_hints(out, ctx=None).is_ok


def test_valid_column_letter_and_mode_ok() -> None:
    out = LayoutHints(identity_column_suggestion="B", mode_suggestion="row_per_pli")
    assert validate_layout_hints(out, ctx=None).is_ok


def test_multi_letter_column_ok() -> None:
    out = LayoutHints(identity_column_suggestion="AA")
    assert validate_layout_hints(out, ctx=None).is_ok


def test_all_three_modes_accepted() -> None:
    for mode in ("row_per_pli", "section_per_pli", "sheet_is_pli"):
        out = LayoutHints(mode_suggestion=mode)
        assert validate_layout_hints(out, ctx=None).is_ok, f"mode {mode!r} should be ok"


# ---------------------------------------------------------------------------
# rejection paths — identity_column_suggestion
# ---------------------------------------------------------------------------

def test_lowercase_column_letter_triggers_retry() -> None:
    out = LayoutHints(identity_column_suggestion="b")
    verdict = validate_layout_hints(out, ctx=None)
    assert verdict.is_retry
    assert "b" in verdict.reason


def test_column_with_digits_triggers_retry() -> None:
    out = LayoutHints(identity_column_suggestion="B2")
    verdict = validate_layout_hints(out, ctx=None)
    assert verdict.is_retry
    assert "B2" in verdict.reason


def test_empty_string_column_triggers_retry() -> None:
    out = LayoutHints(identity_column_suggestion="")
    verdict = validate_layout_hints(out, ctx=None)
    assert verdict.is_retry


# ---------------------------------------------------------------------------
# rejection paths — mode_suggestion
# ---------------------------------------------------------------------------

def test_unknown_mode_triggers_retry() -> None:
    out = LayoutHints(mode_suggestion="SHEET_IS_PLI")
    verdict = validate_layout_hints(out, ctx=None)
    assert verdict.is_retry
    assert "SHEET_IS_PLI" in verdict.reason


def test_garbage_mode_triggers_retry() -> None:
    out = LayoutHints(mode_suggestion="tabular")
    verdict = validate_layout_hints(out, ctx=None)
    assert verdict.is_retry
    assert "tabular" in verdict.reason
