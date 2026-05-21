"""PlanReviewer Haystack component — self-aware: passthrough + LLM path + fallback."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from structlog.testing import capture_logs

from app.components.plan_reviewer import PlanReviewer
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import RowSpec, SheetPlan, ValidationFinding
from app.tools._registry import TOOL_REGISTRY
from tests.fixtures.fake_llm import FakeLLM


def _patch_peek_sheet(monkeypatch) -> None:
    monkeypatch.setitem(
        TOOL_REGISTRY._tools, "peek_sheet",
        lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]),
    )


def _plan(confidence: float = 0.9) -> SheetPlan:
    return SheetPlan(
        sheet="S1",
        pli_mode=PliMode.ROW_PER_PLI,
        stage_scope=StageScope.SHEET_LEVEL,
        header_rows=[1],
        rows=[RowSpec(idx=1, role=RowRole.HEADER), RowSpec(idx=2, role=RowRole.ANCHOR)],
        pli_blocks=[],
        kv_anchors=[],
        stage_bands=[],
        confidence=confidence,
    )


def _warn_finding() -> ValidationFinding:
    return ValidationFinding(
        check="sequence_match", severity=ValidationSeverity.WARN, message="test warn",
    )


def test_passthrough_when_no_trigger_conditions() -> None:
    """High confidence + ROW_PER_PLI + no warnings → plan returned unchanged."""
    llm = FakeLLM(canned={})
    comp = PlanReviewer(llm=llm)
    plan = _plan(confidence=0.95)
    out = comp.run(workbook_ctx=MagicMock(), plan=plan, findings=[])
    assert out["plan"] is plan  # exact same object


def test_llm_invoked_on_warns(monkeypatch) -> None:
    """WARN findings present → LLM invoked → looks_correct verdict → plan unchanged."""
    _patch_peek_sheet(monkeypatch)
    llm = FakeLLM(canned={"PlanVerdict": {"verdict": "looks_correct", "confidence": 0.9}})
    comp = PlanReviewer(llm=llm)
    with capture_logs():
        out = comp.run(workbook_ctx=MagicMock(), plan=_plan(), findings=[_warn_finding()])
    assert isinstance(out["plan"], SheetPlan)


def test_row_corrections_applied(monkeypatch) -> None:
    """needs_fix verdict with valid correction → row role updated in returned plan."""
    _patch_peek_sheet(monkeypatch)
    llm = FakeLLM(canned={"PlanVerdict": {
        "verdict": "needs_fix",
        "row_corrections": [{"row": 2, "suggested_role": "header"}],
    }})
    comp = PlanReviewer(llm=llm)
    with capture_logs():
        out = comp.run(workbook_ctx=MagicMock(), plan=_plan(), findings=[_warn_finding()])
    row2 = next(r for r in out["plan"].rows if r.idx == 2)
    assert row2.role is RowRole.HEADER


def test_fallback_on_agent_failure(monkeypatch) -> None:
    """Agent returns invalid row index → exhausted → plan returned unchanged."""
    _patch_peek_sheet(monkeypatch)
    llm = FakeLLM(canned={"PlanVerdict": {
        "verdict": "needs_fix",
        "row_corrections": [{"row": 99, "suggested_role": "anchor"}],
    }})
    comp = PlanReviewer(llm=llm)
    plan = _plan(confidence=0.5)
    with capture_logs():
        out = comp.run(workbook_ctx=MagicMock(), plan=plan, findings=[])
    # fallback: plan rows unchanged
    assert [r.idx for r in out["plan"].rows] == [1, 2]
