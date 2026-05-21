"""SheetClassifier validator unit tests."""
from __future__ import annotations

import types

from app.agents.sheet_classifier.schema import SheetClassifierOutput
from app.agents.sheet_classifier.validators import validate_input, validate_output


# ---------------------------------------------------------------------------
# validate_input
# ---------------------------------------------------------------------------

def test_validate_input_always_ok() -> None:
    verdict = validate_input("anything")
    assert verdict.is_ok


# ---------------------------------------------------------------------------
# validate_output — happy paths
# ---------------------------------------------------------------------------

def test_validate_output_empty_relevant_sheets_ok() -> None:
    out = SheetClassifierOutput(relevant_sheets=[])
    ctx = types.SimpleNamespace(sheet_names=["A", "B"])
    assert validate_output(out, ctx).is_ok


def test_validate_output_subset_of_workbook_ok() -> None:
    out = SheetClassifierOutput(relevant_sheets=["A"])
    ctx = types.SimpleNamespace(sheet_names=["A", "B"])
    assert validate_output(out, ctx).is_ok


def test_validate_output_all_workbook_sheets_ok() -> None:
    out = SheetClassifierOutput(relevant_sheets=["A", "B"])
    ctx = types.SimpleNamespace(sheet_names=["A", "B"])
    assert validate_output(out, ctx).is_ok


def test_validate_output_no_ctx_sheet_names_ok() -> None:
    """When ctx has no sheet_names, the check is skipped (known is empty set)."""
    out = SheetClassifierOutput(relevant_sheets=["ANYTHING"])
    ctx = types.SimpleNamespace()
    assert validate_output(out, ctx).is_ok


def test_validate_output_ctx_none_ok() -> None:
    out = SheetClassifierOutput(relevant_sheets=[])
    assert validate_output(out, None).is_ok


# ---------------------------------------------------------------------------
# validate_output — rejection paths
# ---------------------------------------------------------------------------

def test_validate_output_unknown_sheet_triggers_retry() -> None:
    out = SheetClassifierOutput(relevant_sheets=["GHOST"])
    ctx = types.SimpleNamespace(sheet_names=["A", "B"])
    verdict = validate_output(out, ctx)
    assert verdict.is_retry
    assert "GHOST" in verdict.reason


def test_validate_output_mixed_known_unknown_triggers_retry() -> None:
    out = SheetClassifierOutput(relevant_sheets=["A", "GHOST"])
    ctx = types.SimpleNamespace(sheet_names=["A", "B"])
    verdict = validate_output(out, ctx)
    assert verdict.is_retry
