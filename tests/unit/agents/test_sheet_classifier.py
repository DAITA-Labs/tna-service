"""Tests for app/services/agents/sheet_classifier."""
from unittest.mock import MagicMock
from app.services.agents.sheet_classifier import (
    SheetClassifier, SheetClassifierOutput, SPEC,
)


def test_spec_name_and_schema():
    assert SPEC.name == "sheet_classifier"
    assert SPEC.output_schema is SheetClassifierOutput


def test_classifier_run_passes_through_relevant_sheets():
    fake_llm = MagicMock()
    fake_llm.complete_with_schema.return_value = SheetClassifierOutput(
        relevant_sheets=["MASTER"], notes="skipped lAB and summary",
    )
    fake_llm.model = "claude-sonnet-4-6"
    c = SheetClassifier(llm=fake_llm)
    fake_summary = MagicMock()
    fake_summary.sheet_names = ["MASTER", "lAB", "summary"]
    out = c.run(workbook_ctx=MagicMock(), workbook_summary=fake_summary)
    assert out["relevant_sheets"] == ["MASTER"]
