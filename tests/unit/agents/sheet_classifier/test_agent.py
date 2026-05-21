"""SheetClassifierAgent unit tests."""
from __future__ import annotations

import types

from app.agents._base import AgentRunFailure
from app.agents.sheet_classifier.agent import SheetClassifierAgent
from app.agents.sheet_classifier.schema import SheetClassifierInputs
from app.models.artifacts import WorkbookSummary
from tests.fixtures.fake_llm import FakeLLM


def _make_summary(sheet_names: list[str]) -> WorkbookSummary:
    return WorkbookSummary(
        sheet_count=len(sheet_names),
        sheet_names=sheet_names,
        file_size_kb=10,
    )


def _make_ctx(sheet_names: list[str]) -> object:
    return types.SimpleNamespace(sheet_names=sheet_names)


# ---------------------------------------------------------------------------
# build_input
# ---------------------------------------------------------------------------

def test_build_input_renders_sheet_count() -> None:
    agent = SheetClassifierAgent()
    summary = _make_summary(["A", "B"])
    inputs = SheetClassifierInputs(workbook_summary=summary)
    text = agent.build_input(ctx=None, inputs=inputs)
    assert "2 sheets" in text


def test_build_input_renders_sheet_names() -> None:
    agent = SheetClassifierAgent()
    summary = _make_summary(["Sheet1", "Info"])
    inputs = SheetClassifierInputs(workbook_summary=summary)
    text = agent.build_input(ctx=None, inputs=inputs)
    assert "Sheet1" in text
    assert "Info" in text


def test_build_input_renders_classify_instruction() -> None:
    agent = SheetClassifierAgent()
    summary = _make_summary(["A"])
    inputs = SheetClassifierInputs(workbook_summary=summary)
    text = agent.build_input(ctx=None, inputs=inputs)
    assert "Classify" in text


# ---------------------------------------------------------------------------
# retry-then-ok
# ---------------------------------------------------------------------------

def test_retry_then_ok_second_response_accepted() -> None:
    """First response has GHOST (unknown); second has known sheet A → accepted."""
    agent = SheetClassifierAgent()
    llm = FakeLLM(canned={}).script_responses(
        {"relevant_sheets": ["GHOST"]},
        {"relevant_sheets": ["A"]},
    )
    ctx = _make_ctx(["A", "B"])
    inputs = SheetClassifierInputs(workbook_summary=_make_summary(["A", "B"]))
    result = agent.run(ctx=ctx, inputs=inputs, provider=llm)
    assert not isinstance(result, AgentRunFailure)
    assert result.relevant_sheets == ["A"]


# ---------------------------------------------------------------------------
# failure exhausted
# ---------------------------------------------------------------------------

def test_failure_when_both_responses_bad() -> None:
    """Both responses have unknown sheets; retries exhausted → AgentRunFailure."""
    agent = SheetClassifierAgent()
    llm = FakeLLM(canned={}).script_responses(
        {"relevant_sheets": ["GHOST1"]},
        {"relevant_sheets": ["GHOST2"]},
    )
    ctx = _make_ctx(["A", "B"])
    inputs = SheetClassifierInputs(workbook_summary=_make_summary(["A", "B"]))
    result = agent.run(ctx=ctx, inputs=inputs, provider=llm)
    assert isinstance(result, AgentRunFailure)
    assert result.agent_name == "sheet_classifier"
