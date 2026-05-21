"""FieldNamer emits the train-of-thought log events on every run."""
from __future__ import annotations

from unittest.mock import MagicMock

from structlog.testing import capture_logs

from app.enums.pli_mode import PliMode
from app.enums.stage_scope import StageScope
from app.models.artifacts import SheetPlan
from app.components.per_sheet.field_namer import FieldNamer
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
    """Return a minimal ctx mock with a wb attribute for FieldNamer._build_user_input."""
    ws = MagicMock()
    ctx = MagicMock()
    ctx.wb.__getitem__ = MagicMock(return_value=ws)
    return ctx


def test_field_namer_emits_capture_logs() -> None:
    llm = FakeLLM(canned={"CanonicalNameMap": {}})
    ctx = _make_ctx()

    with capture_logs() as caps:
        FieldNamer(llm=llm).run(workbook_ctx=ctx, plan=_min_plan())

    log_events = {c["event"] for c in caps}
    assert "agent.input" in log_events
    assert "agent.output" in log_events
