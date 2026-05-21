"""LayoutHinterInputs and LayoutHints schema tests."""
from __future__ import annotations

from app.agents.layout_hinter.schema import LayoutHinterInputs, LayoutHints
from app.artifacts.agent_io import AgentOutput
from app.models.artifacts import SheetSignals


def test_hints_inherits_agent_output() -> None:
    assert issubclass(LayoutHints, AgentOutput)


def test_hints_defaults() -> None:
    out = LayoutHints()
    assert out.identity_column_suggestion is None
    assert out.mode_suggestion is None
    assert out.notes == []
    assert out.decision_notes is None


def test_hints_round_trip() -> None:
    out = LayoutHints(
        identity_column_suggestion="B",
        mode_suggestion="row_per_pli",
        notes=["used header vocab hit"],
    )
    dumped = out.model_dump()
    restored = LayoutHints(**dumped)
    assert restored.identity_column_suggestion == "B"
    assert restored.mode_suggestion == "row_per_pli"
    assert restored.notes == ["used header vocab hit"]


def test_inputs_wraps_sheet_signals() -> None:
    signals = SheetSignals(sheet="Sheet1", max_row=100, max_col=10)
    inputs = LayoutHinterInputs(sheet="Sheet1", signals=signals)
    assert inputs.sheet == "Sheet1"
    assert inputs.signals is signals
