"""SheetClassifier emits the train-of-thought log events on every run."""
from __future__ import annotations

from structlog.testing import capture_logs

from app.services.agents.sheet_classifier import SheetClassifier
from app.models.artifacts import WorkbookSummary
from tests.fixtures.fake_llm import FakeLLM


def test_sheet_classifier_emits_capture_logs() -> None:
    llm = FakeLLM(canned={"SheetClassifierOutput": {"relevant_sheets": ["S1"]}})
    summary = WorkbookSummary(sheet_count=1, sheet_names=["S1"], file_size_kb=1)

    with capture_logs() as caps:
        SheetClassifier(llm=llm).run(workbook_ctx=None, workbook_summary=summary)

    log_events = {c["event"] for c in caps}
    assert "agent.input" in log_events
    assert "agent.output" in log_events
