"""SheetClassifier component unit tests."""
from __future__ import annotations

from app.components.workbook.sheet_classifier import SheetClassifier
from app.models.artifacts import WorkbookSummary
from tests.fixtures.fake_llm import FakeLLM


def _make_summary(sheet_names: list[str]) -> WorkbookSummary:
    return WorkbookSummary(
        sheet_count=len(sheet_names),
        sheet_names=sheet_names,
        file_size_kb=5,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_component_returns_relevant_sheets_from_agent() -> None:
    llm = FakeLLM(canned={"SheetClassifierOutput": {"relevant_sheets": ["TNA"]}})
    summary = _make_summary(["TNA", "info"])
    component = SheetClassifier(llm=llm)
    result = component.run(workbook_ctx=None, workbook_summary=summary)
    assert result["relevant_sheets"] == ["TNA"]


# ---------------------------------------------------------------------------
# Agent failure falls back to all sheets
# ---------------------------------------------------------------------------

def test_component_falls_back_to_all_sheets_on_agent_failure() -> None:
    """When the agent exhausts retries, component returns all workbook sheet names."""
    # Script two bad responses so both attempts fail semantic validation.
    llm = FakeLLM(canned={}).script_responses(
        {"relevant_sheets": ["GHOST1"]},
        {"relevant_sheets": ["GHOST2"]},
    )
    summary = _make_summary(["A", "B"])
    component = SheetClassifier(llm=llm)
    result = component.run(workbook_ctx=None, workbook_summary=summary)
    assert set(result["relevant_sheets"]) == {"A", "B"}
