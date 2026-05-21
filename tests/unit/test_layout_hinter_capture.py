"""LayoutHinter emits the train-of-thought log events on every run."""
from __future__ import annotations

from unittest.mock import MagicMock

from structlog.testing import capture_logs

import app.tools.bulk_read  # noqa: F401 — register peek_sheet
from app.models.artifacts import LayoutHints, SheetSignals
from app.components.layout_hinter import LayoutHinter
from tests.fixtures.fake_llm import FakeLLM


def _make_ctx(sheet: str) -> MagicMock:
    """Return a minimal ctx mock whose wb[sheet] responds to peek_sheet calls."""
    ws = MagicMock()
    ws.max_row = 0
    ws.max_column = 0
    ctx = MagicMock()
    ctx.wb.__getitem__ = MagicMock(return_value=ws)
    return ctx


def test_layout_hinter_emits_capture_logs() -> None:
    llm = FakeLLM(canned={"LayoutHints": {}})
    ctx = _make_ctx("S1")
    signals = SheetSignals(sheet="S1", max_row=0, max_col=0)

    with capture_logs() as caps:
        LayoutHinter(llm=llm).run(workbook_ctx=ctx, sheet="S1", signals=signals)

    log_events = {c["event"] for c in caps}
    assert "agent.input" in log_events
    assert "agent.output" in log_events
