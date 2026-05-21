"""FieldNamer Haystack component — happy path + fallback."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.components.per_sheet.field_namer import FieldNamer
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.models.artifacts import CanonicalNameMap, HeaderLabel, RowSpec, SheetPlan
from tests.fixtures.fake_llm import FakeLLM


def _plan() -> SheetPlan:
    return SheetPlan(
        sheet="S1",
        pli_mode=PliMode.ROW_PER_PLI,
        stage_scope=StageScope.SHEET_LEVEL,
        header_rows=[1],
        header_labels=[HeaderLabel(raw="Job #", col="A", row=1, confidence=1.0)],
        rows=[RowSpec(idx=1, role=RowRole.HEADER), RowSpec(idx=2, role=RowRole.ANCHOR)],
        pli_blocks=[],
        kv_anchors=[],
        stage_bands=[],
        confidence=0.9,
    )


def test_component_happy_path() -> None:
    """Agent returns a valid CanonicalNameMap → propagated."""
    llm = FakeLLM(canned={"CanonicalNameMap": {"field_labels": {"Job #": "io_number"}}})
    comp = FieldNamer(llm=llm)
    ctx = MagicMock()
    del ctx.wb
    out = comp.run(workbook_ctx=ctx, plan=_plan())
    assert out["name_map"].field_labels["Job #"] == "io_number"


def test_component_falls_back_on_failure() -> None:
    """Agent failure → empty CanonicalNameMap fallback."""
    # canned response maps to a non-canonical name → validate_output retries each time
    llm = FakeLLM(canned={"CanonicalNameMap": {"field_labels": {"X": "non_canonical"}}})
    comp = FieldNamer(llm=llm)
    ctx = MagicMock()
    del ctx.wb
    out = comp.run(workbook_ctx=ctx, plan=_plan())
    assert isinstance(out["name_map"], CanonicalNameMap)
    assert out["name_map"].field_labels == {}  # empty fallback
