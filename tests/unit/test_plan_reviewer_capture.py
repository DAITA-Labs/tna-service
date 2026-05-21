"""PlanReviewer emits the parsed verdict as agent.output before any caller mutates it."""
from __future__ import annotations

from unittest.mock import MagicMock

from structlog.testing import capture_logs

import app.repositories.workbook_tools.bulk_read  # noqa: F401 — register peek_sheet
from app.enums.pli_mode import PliMode
from app.enums.stage_scope import StageScope
from app.models.artifacts import SheetPlan
from app.services.agents.plan_reviewer import PlanReviewer
from tests.fixtures.fake_llm import FakeLLM


def _min_plan() -> SheetPlan:
    return SheetPlan(
        sheet="S1",
        pli_mode=PliMode.ROW_PER_PLI,
        stage_scope=StageScope.SHEET_LEVEL,
        header_rows=[],
        rows=[],
        pli_blocks=[],
        kv_anchors=[],
        stage_bands=[],
        confidence=0.9,
    )


def _make_ctx() -> MagicMock:
    """Return a minimal ctx mock whose wb[sheet] responds to peek_sheet calls."""
    ws = MagicMock()
    ws.max_row = 0
    ws.max_column = 0
    ctx = MagicMock()
    ctx.wb.__getitem__ = MagicMock(return_value=ws)
    return ctx


def test_plan_reviewer_logs_parsed_verdict_before_apply() -> None:
    llm = FakeLLM(canned={"PlanVerdict": {"verdict": "looks_correct"}})
    ctx = _make_ctx()

    with capture_logs() as caps:
        PlanReviewer(llm=llm).run(workbook_ctx=ctx, plan=_min_plan(), findings=[])

    out_events = [c for c in caps if c["event"] == "agent.output"]
    assert len(out_events) == 1
    assert out_events[0]["payload"]["verdict"] == "looks_correct"
