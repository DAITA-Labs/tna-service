"""SheetClassifierInputs and SheetClassifierOutput schema tests."""
from __future__ import annotations

from app.agents.sheet_classifier.schema import SheetClassifierInputs, SheetClassifierOutput
from app.artifacts.agent_io import AgentOutput


def test_output_inherits_agent_output() -> None:
    assert issubclass(SheetClassifierOutput, AgentOutput)


def test_output_defaults() -> None:
    out = SheetClassifierOutput()
    assert out.relevant_sheets == []
    assert out.notes is None
    assert out.decision_notes is None


def test_output_round_trip() -> None:
    out = SheetClassifierOutput(relevant_sheets=["A", "B"], notes="ok")
    dumped = out.model_dump()
    restored = SheetClassifierOutput(**dumped)
    assert restored.relevant_sheets == ["A", "B"]
    assert restored.notes == "ok"


def test_inputs_wraps_summary() -> None:
    """SheetClassifierInputs holds the workbook_summary without restriction."""
    from app.models.artifacts import WorkbookSummary

    summary = WorkbookSummary(sheet_count=2, sheet_names=["X", "Y"], file_size_kb=10)
    inputs = SheetClassifierInputs(workbook_summary=summary)
    assert inputs.workbook_summary is summary
