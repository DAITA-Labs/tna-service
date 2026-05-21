"""LayoutHinter emits train-of-thought log events when the LLM path is triggered."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from structlog.testing import capture_logs

import app.tools.bulk_read  # noqa: F401 — register peek_sheet
from app.components.layout_hinter import LayoutHinter
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import RowSpec, SheetPlan, SheetSignals, ValidationFinding
from app.tools._registry import TOOL_REGISTRY
from tests.fixtures.fake_llm import FakeLLM


def _make_ctx(sheet: str) -> MagicMock:
    """Return a minimal ctx mock whose wb[sheet] responds to peek_sheet calls."""
    ws = MagicMock()
    ws.max_row = 0
    ws.max_column = 0
    ctx = MagicMock()
    ctx.wb.__getitem__ = MagicMock(return_value=ws)
    return ctx


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


def test_layout_hinter_emits_capture_logs(monkeypatch) -> None:
    """When Tier-1 errors force the LLM path, agent.input and agent.output are logged."""
    monkeypatch.setattr(
        "app.components.layout_hinter.survey_sheet",
        lambda ctx, sheet: SheetSignals(sheet="S1", max_row=0, max_col=0),
    )
    llm = FakeLLM(canned={"LayoutHints": {}})
    ctx = _make_ctx("S1")
    error_finding = ValidationFinding(
        check="test", severity=ValidationSeverity.ERROR, message="force hinter",
    )
    with capture_logs() as caps:
        LayoutHinter(llm=llm).run(
            workbook_ctx=ctx, plan=_plan(), findings=[error_finding], sheet="S1",
        )
    log_events = {c["event"] for c in caps}
    assert "agent.input" in log_events
    assert "agent.output" in log_events
