"""Unit tests for new wrapper components: Planner, PlanValidator, Applier (component),
PostReviewValidator, PostNamerValidator, PreApplyValidator, ExtractionResultBuilder,
Reconciler (component), WorkbookSummaryProvider.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from structlog.testing import capture_logs

import openpyxl

from app.components.per_sheet.applier import Applier
from app.components.workbook.extraction_result_builder import ExtractionResultBuilder
from app.components.per_sheet.plan_validator import PlanValidator
from app.components.per_sheet.planner import Planner
from app.components.validators.post_namer_validator import PostNamerValidator
from app.components.validators.post_review_validator import PostReviewValidator
from app.components.validators.pre_apply_validator import PreApplyValidator
from app.components.workbook.reconciler import Reconciler
from app.components.workbook.summary_provider import WorkbookSummaryProvider
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import (
    CanonicalNameMap,
    HeaderLabel,
    RowSpec,
    SheetPlan,
    ValidationFinding,
    ValidationFindings,
)
from app.models.extraction import ExtractionResult, Warning
from app.tools._registry import TOOL_REGISTRY


def _simple_plan(sheet: str = "S1") -> SheetPlan:
    return SheetPlan(
        sheet=sheet,
        pli_mode=PliMode.ROW_PER_PLI,
        stage_scope=StageScope.SHEET_LEVEL,
        header_rows=[1],
        rows=[
            RowSpec(idx=1, role=RowRole.HEADER),
            RowSpec(idx=2, role=RowRole.ANCHOR),
        ],
        pli_blocks=[],
        kv_anchors=[],
        stage_bands=[],
        confidence=0.9,
        header_labels=[HeaderLabel(raw="IO No", col="A", row=1)],
    )


# ---- WorkbookSummaryProvider ----

def test_workbook_summary_provider_calls_tool(monkeypatch) -> None:
    """Confirm the component delegates to the workbook_summary tool."""
    fake_summary = SimpleNamespace(sheet_count=1, sheet_names=["Plan"], file_size_kb=10)
    monkeypatch.setitem(
        TOOL_REGISTRY._tools,
        "workbook_summary",
        lambda ctx: fake_summary,
    )
    comp = WorkbookSummaryProvider()
    out = comp.run(workbook_ctx=MagicMock())
    assert out["summary"] is fake_summary


# ---- Planner ----

def test_planner_delegates_to_sheet_row_planner() -> None:
    """Planner.run() should call SheetRowPlanner.run() and unwrap plan."""
    fake_plan = _simple_plan()
    with patch("app.components.per_sheet.planner.SheetRowPlanner") as MockPlanner:
        MockPlanner.return_value.run.return_value = {"plan": fake_plan}
        comp = Planner()
        out = comp.run(workbook_ctx=MagicMock(), sheet="S1")
    assert out["plan"] is fake_plan


# ---- PlanValidator ----

def test_plan_validator_returns_plan_and_findings(monkeypatch) -> None:
    """PlanValidator aggregates t1 + t2 findings and passes plan through."""
    plan = _simple_plan()
    # Build a minimal real workbook ctx so validate_statistics doesn't crash
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S1"
    ctx = SimpleNamespace(wb=wb)

    comp = PlanValidator()
    with capture_logs():
        out = comp.run(workbook_ctx=ctx, plan=plan)
    assert out["plan"] is plan
    assert isinstance(out["findings"], list)


# ---- PostReviewValidator ----

def test_post_review_validator_passes_plan_through() -> None:
    """PostReviewValidator runs validate_post_review and passes plan."""
    plan = _simple_plan()
    comp = PostReviewValidator()
    with capture_logs():
        out = comp.run(plan=plan)
    assert out["plan"] is plan
    assert isinstance(out["findings"], list)


# ---- PostNamerValidator ----

def test_post_namer_validator_flags_missing_label() -> None:
    """PostNamerValidator emits a warning for an unmapped label."""
    plan = _simple_plan()
    name_map = CanonicalNameMap()  # empty — won't map "IO No"
    comp = PostNamerValidator()
    with capture_logs():
        out = comp.run(plan=plan, name_map=name_map)
    assert out["name_map"] is name_map
    assert any("IO No" in f.message for f in out["findings"])


# ---- PreApplyValidator ----

def test_pre_apply_validator_errors_when_header_labels_empty() -> None:
    """PreApplyValidator raises ERROR when ROW_PER_PLI plan has empty header_labels."""
    plan = _simple_plan()
    plan = plan.model_copy(update={"header_labels": []})
    comp = PreApplyValidator()
    out = comp.run(plan=plan)
    errors = [f for f in out["findings"] if f.severity is ValidationSeverity.ERROR]
    assert errors


def test_pre_apply_validator_passes_clean_plan() -> None:
    """PreApplyValidator produces no findings for a valid plan."""
    plan = _simple_plan()
    comp = PreApplyValidator()
    out = comp.run(plan=plan)
    errors = [f for f in out["findings"] if f.severity is ValidationSeverity.ERROR]
    assert not errors


# ---- Applier (component) ----

def test_applier_blocks_on_pre_apply_errors() -> None:
    """Applier returns empty plis + error warnings when pre_apply has errors."""
    plan = _simple_plan()
    name_map = CanonicalNameMap()
    error_finding = ValidationFinding(
        check="pre_apply", severity=ValidationSeverity.ERROR, message="blocked",
    )
    comp = Applier()
    out = comp.run(
        workbook_ctx=MagicMock(),
        plan=plan,
        name_map=name_map,
        findings_pre_apply=[error_finding],
    )
    assert out["plis"] == []
    assert out["warnings"]
    assert out["warnings"][0].severity == "error"


def test_applier_delegates_to_apply_plan_when_clean() -> None:
    """Applier calls apply_plan when no pre_apply errors."""
    plan = _simple_plan()
    name_map = CanonicalNameMap()
    # Build a minimal workbook that apply_plan won't crash on
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S1"
    ws.cell(row=2, column=1).value = "IO-001"
    ctx = SimpleNamespace(wb=wb)

    comp = Applier()
    with capture_logs():
        out = comp.run(workbook_ctx=ctx, plan=plan, name_map=name_map, findings_pre_apply=[])
    assert isinstance(out["plis"], list)
    assert out["warnings"] == []


# ---- ExtractionResultBuilder ----

def test_extraction_result_builder_assembles_result() -> None:
    """ExtractionResultBuilder wraps plis + warnings into ExtractionResult."""
    comp = ExtractionResultBuilder()
    out = comp.run(plis=[], warnings=[], format_detected="row_per_pli", source_file="x.xlsx")
    result = out["result"]
    assert isinstance(result, ExtractionResult)
    assert result.source_file == "x.xlsx"
    assert result.format_detected == "row_per_pli"


# ---- Reconciler (component) ----

def test_reconciler_component_merges_findings() -> None:
    """Reconciler appends validator findings as warnings to the workflow result."""
    workflow = ExtractionResult(plis=[], source_file="x.xlsx")
    finding = ValidationFinding(
        check="source_cell", severity=ValidationSeverity.WARN, message="drift",
    )
    comp = Reconciler()
    with capture_logs():
        out = comp.run(
            workflow_out=workflow,
            source_findings=ValidationFindings(findings=[finding]),
            header_findings=ValidationFindings(findings=[]),
            coverage_findings=ValidationFindings(findings=[]),
            dropout_findings=ValidationFindings(findings=[]),
        )
    result = out["result"]
    assert any("drift" in w.message for w in result.warnings)
