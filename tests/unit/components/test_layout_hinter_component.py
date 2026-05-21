"""LayoutHinter Haystack component — happy path + fallback."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.components.layout_hinter import LayoutHinter
from app.models.artifacts import SheetSignals
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from tests.fixtures.fake_llm import FakeLLM


def _patch_peek_sheet(monkeypatch) -> None:
    """Replace peek_sheet with a no-op fixture."""
    monkeypatch.setitem(
        TOOL_REGISTRY._tools,
        "peek_sheet",
        lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]),
    )


def test_component_returns_hints_dict(monkeypatch) -> None:
    """Happy path: agent succeeds → hints in output dict."""
    _patch_peek_sheet(monkeypatch)
    llm = FakeLLM(canned={"LayoutHints": {"identity_column_suggestion": "K"}})
    comp = LayoutHinter(llm=llm)
    out = comp.run(workbook_ctx=MagicMock(), sheet="Plan", signals=SheetSignals(sheet="Plan", max_row=10, max_col=10))
    assert out["hints"].identity_column_suggestion == "K"


def test_component_falls_back_on_failure(monkeypatch) -> None:
    """Agent failure → empty LayoutHints fallback."""
    _patch_peek_sheet(monkeypatch)
    # Both scripted responses fail validate_output (lowercase letter) → exhausted → fallback.
    llm = FakeLLM(canned={}).script_responses(
        {"identity_column_suggestion": "lower"},
        {"identity_column_suggestion": "also_lower"},
    )
    comp = LayoutHinter(llm=llm)
    out = comp.run(workbook_ctx=MagicMock(), sheet="Plan", signals=SheetSignals(sheet="Plan", max_row=10, max_col=10))
    assert out["hints"].identity_column_suggestion is None
