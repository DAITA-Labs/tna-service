"""PlanReviewerAgent build_input + retry behaviour."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agents._base import AgentRunFailure
from app.agents.plan_reviewer import PlanReviewerAgent, PlanReviewerInputs, PlanVerdict
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.models.artifacts import RowSpec, SheetPlan
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from tests.fixtures.fake_llm import FakeLLM


def _patch_peek_sheet(monkeypatch) -> None:
    """Replace peek_sheet with a fixed no-cell grid."""
    monkeypatch.setitem(
        TOOL_REGISTRY._tools, "peek_sheet",
        lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]),
    )


def _minimal_plan() -> SheetPlan:
    """Build a tiny SheetPlan with three rows for ctx.plan_rows fixtures."""
    return SheetPlan(
        sheet="S1",
        pli_mode=PliMode.ROW_PER_PLI,
        stage_scope=StageScope.SHEET_LEVEL,
        header_rows=[1],
        rows=[
            RowSpec(idx=1, role=RowRole.HEADER),
            RowSpec(idx=2, role=RowRole.ANCHOR),
            RowSpec(idx=3, role=RowRole.ANCHOR),
        ],
        pli_blocks=[],
        kv_anchors=[],
        stage_bands=[],
        confidence=0.9,
    )


def test_build_input_includes_sheet_plan_and_warnings(monkeypatch) -> None:
    """build_input renders sheet name, plan dump, findings, and peek section."""
    _patch_peek_sheet(monkeypatch)
    agent = PlanReviewerAgent()
    plan = _minimal_plan()
    inputs = PlanReviewerInputs(plan=plan, findings=[])
    text = agent.build_input(MagicMock(), inputs)
    assert "# Sheet: S1" in text
    assert "## Plan summary:" in text
    assert "## Tier 1/2 warnings:" in text
    assert "## Sheet peek" in text


def test_retries_when_row_correction_unknown(monkeypatch) -> None:
    """First response references a non-existent row → retry; second response passes."""
    _patch_peek_sheet(monkeypatch)
    bad = {"verdict": "needs_fix", "row_corrections": [{"row": 99, "suggested_role": "anchor"}], "confidence": 0.9}
    good = {"verdict": "looks_correct", "confidence": 0.9}
    llm = FakeLLM(canned={}).script_responses(bad, good)
    agent = PlanReviewerAgent()
    plan = _minimal_plan()
    ctx = MagicMock()
    ctx.plan_rows = [r.idx for r in plan.rows]
    result = agent.run(
        ctx=ctx,
        inputs=PlanReviewerInputs(plan=plan, findings=[]),
        provider=llm,
    )
    assert isinstance(result, PlanVerdict)
    assert result.verdict == "looks_correct"


def test_failure_after_retry_exhausted(monkeypatch) -> None:
    """Both responses semantic-fail → AgentRunFailure."""
    _patch_peek_sheet(monkeypatch)
    bad1 = {"verdict": "needs_fix", "row_corrections": [{"row": 99, "suggested_role": "anchor"}]}
    bad2 = {"verdict": "needs_fix", "row_corrections": [{"row": 100, "suggested_role": "anchor"}]}
    llm = FakeLLM(canned={}).script_responses(bad1, bad2)
    agent = PlanReviewerAgent()
    plan = _minimal_plan()
    ctx = MagicMock()
    ctx.plan_rows = [r.idx for r in plan.rows]
    result = agent.run(
        ctx=ctx,
        inputs=PlanReviewerInputs(plan=plan, findings=[]),
        provider=llm,
    )
    assert isinstance(result, AgentRunFailure)
