"""LayoutHinter Haystack component — self-aware: passthrough + LLM path + fallback."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from structlog.testing import capture_logs

from app.components.per_sheet.layout_hinter import LayoutHinter
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import RowSpec, SheetPlan, SheetSignals, ValidationFinding
from app.tools._registry import TOOL_REGISTRY
from tests.fixtures.fake_llm import FakeLLM

_STUB_SIGNALS = SheetSignals(sheet="S1", max_row=10, max_col=10)


def _patch_peek_sheet(monkeypatch) -> None:
    """Replace peek_sheet with a no-op fixture."""
    monkeypatch.setitem(
        TOOL_REGISTRY._tools,
        "peek_sheet",
        lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]),
    )


def _patch_survey(monkeypatch) -> None:
    """Replace survey_sheet with stub signals."""
    monkeypatch.setattr(
        "app.components.per_sheet.layout_hinter.survey_sheet",
        lambda ctx, sheet: _STUB_SIGNALS,
    )


def _plan() -> SheetPlan:
    return SheetPlan(
        sheet="S1",
        pli_mode=PliMode.ROW_PER_PLI,
        stage_scope=StageScope.SHEET_LEVEL,
        header_rows=[1],
        rows=[RowSpec(idx=1, role=RowRole.HEADER), RowSpec(idx=2, role=RowRole.ANCHOR)],
        pli_blocks=[],
        kv_anchors=[],
        stage_bands=[],
        confidence=0.9,
    )


def _error_finding() -> ValidationFinding:
    return ValidationFinding(
        check="reference_integrity",
        severity=ValidationSeverity.ERROR,
        message="test error",
    )


def test_passthrough_when_no_errors(monkeypatch) -> None:
    """No Tier-1 errors → plan returned unchanged without LLM call."""
    _patch_peek_sheet(monkeypatch)
    llm = FakeLLM(canned={})
    comp = LayoutHinter(llm=llm)
    plan = _plan()
    out = comp.run(workbook_ctx=MagicMock(), plan=plan, findings=[], sheet="S1")
    assert out["plan"] is plan  # exact same object — no LLM called


def test_llm_invoked_and_suggestion_applied(monkeypatch) -> None:
    """Tier-1 error present → LLM invoked → identity_column updated."""
    _patch_peek_sheet(monkeypatch)
    _patch_survey(monkeypatch)
    llm = FakeLLM(canned={"LayoutHints": {"identity_column_suggestion": "K"}})
    comp = LayoutHinter(llm=llm)
    with capture_logs():
        out = comp.run(
            workbook_ctx=MagicMock(),
            plan=_plan(),
            findings=[_error_finding()],
            sheet="S1",
        )
    assert out["plan"].identity_column == "K"


def test_fallback_on_agent_failure(monkeypatch) -> None:
    """Agent exhausts retries → plan returned unchanged (passthrough fallback)."""
    _patch_peek_sheet(monkeypatch)
    _patch_survey(monkeypatch)
    llm = FakeLLM(canned={}).script_responses(
        {"identity_column_suggestion": "lower"},
        {"identity_column_suggestion": "also_lower"},
    )
    comp = LayoutHinter(llm=llm)
    plan = _plan()
    with capture_logs():
        out = comp.run(
            workbook_ctx=MagicMock(),
            plan=plan,
            findings=[_error_finding()],
            sheet="S1",
        )
    assert out["plan"].identity_column is None  # unchanged — fallback
