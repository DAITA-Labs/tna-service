"""FieldNamerAgent build_input across modes + retry behaviour."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.agents._base import AgentRunFailure
from app.agents.field_namer import CanonicalNameMap, FieldNamerAgent, FieldNamerInputs
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.models.artifacts import HeaderLabel, KVAnchor, RowSpec, SheetPlan
from tests.fixtures.fake_llm import FakeLLM


def _row_per_pli_plan() -> SheetPlan:
    """Build a tiny ROW_PER_PLI SheetPlan with one header label."""
    return SheetPlan(
        sheet="S1",
        pli_mode=PliMode.ROW_PER_PLI,
        stage_scope=StageScope.SHEET_LEVEL,
        header_rows=[1],
        header_labels=[HeaderLabel(raw="Job #", col="A", row=1, confidence=1.0)],
        rows=[
            RowSpec(idx=1, role=RowRole.HEADER),
            RowSpec(idx=2, role=RowRole.ANCHOR),
        ],
        pli_blocks=[],
        kv_anchors=[],
        stage_bands=[],
        confidence=0.9,
    )


def _sheet_is_pli_plan() -> SheetPlan:
    """Build a tiny SHEET_IS_PLI SheetPlan with one KV anchor."""
    return SheetPlan(
        sheet="S2",
        pli_mode=PliMode.SHEET_IS_PLI,
        stage_scope=StageScope.PLI_LOCAL,
        header_rows=[],
        rows=[],
        pli_blocks=[],
        kv_anchors=[KVAnchor(label_cell="A1", value_cell="B1", field="Job No")],
        stage_bands=[],
        confidence=0.9,
    )


def test_build_input_row_per_pli_includes_header_labels() -> None:
    """build_input emits Identity labels detected including header_labels for ROW_PER_PLI."""
    agent = FieldNamerAgent()
    plan = _row_per_pli_plan()
    ctx = MagicMock()
    # ctx.wb missing → samples skipped; build_input still works
    del ctx.wb
    text = agent.build_input(ctx, FieldNamerInputs(plan=plan))
    assert "# Sheet: S1" in text
    assert "'Job #' (col A)" in text
    assert "## Identity labels detected" in text


def test_build_input_sheet_is_pli_uses_kv_anchors() -> None:
    """build_input reads from kv_anchors for SHEET_IS_PLI."""
    agent = FieldNamerAgent()
    plan = _sheet_is_pli_plan()
    ctx = MagicMock()
    del ctx.wb
    text = agent.build_input(ctx, FieldNamerInputs(plan=plan))
    assert "'Job No' (col A)" in text


def test_retries_when_validate_output_rejects() -> None:
    """First response maps to a non-canonical name → retry; second response passes."""
    bad = {"field_labels": {"Job #": "made_up"}}
    good = {"field_labels": {"Job #": "io_number"}}
    llm = FakeLLM(canned={}).script_responses(bad, good)
    agent = FieldNamerAgent()
    plan = _row_per_pli_plan()
    ctx = MagicMock()
    del ctx.wb
    result = agent.run(
        ctx=ctx,
        inputs=FieldNamerInputs(plan=plan),
        provider=llm,
    )
    assert isinstance(result, CanonicalNameMap)
    assert result.field_labels["Job #"] == "io_number"


def test_failure_after_retry_exhausted() -> None:
    """Both responses non-canonical → AgentRunFailure."""
    llm = FakeLLM(canned={}).script_responses(
        {"field_labels": {"X": "made_up_one"}},
        {"field_labels": {"X": "made_up_two"}},
    )
    agent = FieldNamerAgent()
    plan = _row_per_pli_plan()
    ctx = MagicMock()
    del ctx.wb
    result = agent.run(
        ctx=ctx,
        inputs=FieldNamerInputs(plan=plan),
        provider=llm,
    )
    assert isinstance(result, AgentRunFailure)
