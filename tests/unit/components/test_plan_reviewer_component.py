"""PlanReviewer Haystack component — happy path + fallback."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.components.plan_reviewer import PlanReviewer
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.models.artifacts import PlanVerdict, RowSpec, SheetPlan
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from tests.fixtures.fake_llm import FakeLLM


def _patch_peek_sheet(monkeypatch) -> None:
    monkeypatch.setitem(
        TOOL_REGISTRY._tools, "peek_sheet",
        lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]),
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


def test_component_happy_path(monkeypatch) -> None:
    """Agent returns a valid verdict → propagated through the component."""
    _patch_peek_sheet(monkeypatch)
    llm = FakeLLM(canned={"PlanVerdict": {"verdict": "looks_correct", "confidence": 0.9}})
    comp = PlanReviewer(llm=llm)
    out = comp.run(workbook_ctx=MagicMock(), plan=_plan(), findings=[])
    assert isinstance(out["verdict"], PlanVerdict)
    assert out["verdict"].verdict == "looks_correct"


def test_component_falls_back_on_failure(monkeypatch) -> None:
    """Agent failure (semantic-fail twice) → low-confidence looks_correct fallback."""
    _patch_peek_sheet(monkeypatch)
    # canned response uses a row index outside plan.rows → validate_output rejects every time
    llm = FakeLLM(canned={"PlanVerdict": {"verdict": "needs_fix", "row_corrections": [{"row": 99, "suggested_role": "anchor"}]}})
    comp = PlanReviewer(llm=llm)
    out = comp.run(workbook_ctx=MagicMock(), plan=_plan(), findings=[])
    assert out["verdict"].verdict == "looks_correct"
    assert out["verdict"].confidence == 0.0  # fallback signature
