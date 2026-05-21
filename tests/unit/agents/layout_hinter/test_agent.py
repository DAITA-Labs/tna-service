"""LayoutHinterAgent build_input + retry behaviour."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agents._base import AgentRunFailure
from app.agents.layout_hinter import LayoutHinterAgent, LayoutHinterInputs, LayoutHints
from app.models.artifacts import SheetSignals
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from tests.fixtures.fake_llm import FakeLLM


def _ctx() -> object:
    """Build a workbook ctx that satisfies the peek_sheet tool fixture."""
    return MagicMock()


def _patch_peek_sheet(monkeypatch) -> None:
    """Replace peek_sheet in the registry with a fixed 0-cell grid."""
    fake_grid = SimpleNamespace(cells=[])

    def _peek(ctx, sheet, rows, cols):
        return fake_grid

    monkeypatch.setitem(TOOL_REGISTRY._tools, "peek_sheet", _peek)


def test_build_input_includes_sheet_and_signals(monkeypatch) -> None:
    """build_input renders sheet, signals dump, and a peek section."""
    _patch_peek_sheet(monkeypatch)
    agent = LayoutHinterAgent()
    inputs = LayoutHinterInputs(sheet="Plan", signals=SheetSignals(sheet="Plan", max_row=10, max_col=10))
    text = agent.build_input(_ctx(), inputs)
    assert "# Sheet: Plan" in text
    assert "## Signals:" in text
    assert "## Top-left peek" in text


def test_retries_when_validate_output_rejects(monkeypatch) -> None:
    """First response is malformed (lowercase) → retry; second response passes."""
    _patch_peek_sheet(monkeypatch)
    bad = {"identity_column_suggestion": "k"}
    good = {"identity_column_suggestion": "K"}
    llm = FakeLLM(canned={}).script_responses(bad, good)
    agent = LayoutHinterAgent()
    inputs = LayoutHinterInputs(sheet="Plan", signals=SheetSignals(sheet="Plan", max_row=10, max_col=10))
    result = agent.run(ctx=_ctx(), inputs=inputs, provider=llm)
    assert isinstance(result, LayoutHints)
    assert result.identity_column_suggestion == "K"


def test_failure_after_retry_exhausted(monkeypatch) -> None:
    """Both responses bad → AgentRunFailure."""
    _patch_peek_sheet(monkeypatch)
    llm = FakeLLM(canned={}).script_responses(
        {"identity_column_suggestion": "a"},
        {"identity_column_suggestion": "b"},
    )
    agent = LayoutHinterAgent()
    inputs = LayoutHinterInputs(sheet="Plan", signals=SheetSignals(sheet="Plan", max_row=10, max_col=10))
    result = agent.run(ctx=_ctx(), inputs=inputs, provider=llm)
    assert isinstance(result, AgentRunFailure)
