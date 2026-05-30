"""extract_canvas_v2() — plan-driven service orchestration tests."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.artifacts.finding import ValidationWarning
from app.models.extraction import ExtractionResult, PLI
from app.services.canvas_extract_v2_service import extract_canvas_v2


def _mock_ctx(tmp_path: Path) -> SimpleNamespace:
    """Fake WorkbookCtx exposing only the attributes the service reads."""
    return SimpleNamespace(path=tmp_path / "fake.xlsx", wb=MagicMock())


# ── Empty-workbook path ─────────────────────────────────────────────────


def test_empty_bundles_returns_no_pli_warning(tmp_path: Path) -> None:
    """Zero clusters → empty PLI list + single 'no PLI clusters' warning."""
    ctx = _mock_ctx(tmp_path)
    with patch("app.services.canvas_extract_v2_service.register_workbook", return_value=ctx), \
         patch("app.services.canvas_extract_v2_service.WorkbookPhase") as MockPhase:
        MockPhase.return_value.run.return_value = {"bundles": []}
        result = extract_canvas_v2(ctx.path)

    assert isinstance(result, ExtractionResult)
    assert result.plis == []
    assert len(result.warnings) == 1
    assert "No PLI clusters" in result.warnings[0].message


def test_source_file_attached_to_result(tmp_path: Path) -> None:
    ctx = _mock_ctx(tmp_path)
    with patch("app.services.canvas_extract_v2_service.register_workbook", return_value=ctx), \
         patch("app.services.canvas_extract_v2_service.WorkbookPhase") as MockPhase:
        MockPhase.return_value.run.return_value = {"bundles": []}
        result = extract_canvas_v2(ctx.path)

    assert result.source_file == str(ctx.path)


# ── Happy path: per-bundle plan → applier merge ─────────────────────────


def test_per_bundle_plis_and_warnings_merge_into_one_result(tmp_path: Path) -> None:
    """Two bundles → both planners + appliers run, PLIs concatenated, warnings mapped."""
    ctx = _mock_ctx(tmp_path)
    bundle_a   = SimpleNamespace(canvas=MagicMock(), anchor_sheet_name="A")
    bundle_b   = SimpleNamespace(canvas=MagicMock(), anchor_sheet_name="B")
    plan_a     = SimpleNamespace(warnings=[ValidationWarning(
        message="trio missing", name="date_trio_all_missing", severity="warning",
    )])
    plan_b     = SimpleNamespace(warnings=[])
    pli_a      = PLI(io_number="IO-A")
    pli_b1     = PLI(io_number="IO-B1")
    pli_b2     = PLI(io_number="IO-B2")

    def planner_run(bundle):
        return {"plan": plan_a if bundle is bundle_a else plan_b}

    def applier_run(plan, canvas, sheet):
        return {"plis": [pli_a] if plan is plan_a else [pli_b1, pli_b2]}

    with patch("app.services.canvas_extract_v2_service.register_workbook", return_value=ctx), \
         patch("app.services.canvas_extract_v2_service.WorkbookPhase") as MockPhase, \
         patch("app.services.canvas_extract_v2_service.PlanAssembler") as MockPlanner, \
         patch("app.services.canvas_extract_v2_service.CanvasApplier") as MockApplier:
        MockPhase.return_value.run.return_value          = {"bundles": [bundle_a, bundle_b]}
        MockPlanner.return_value.run.side_effect          = planner_run
        MockApplier.return_value.run.side_effect          = applier_run
        result = extract_canvas_v2(ctx.path)

    assert [p.io_number for p in result.plis] == ["IO-A", "IO-B1", "IO-B2"]
    assert len(result.warnings) == 1
    assert result.warnings[0].check    == "date_trio_all_missing"
    assert result.warnings[0].severity == "warning"


def test_applier_receives_bundle_canvas_and_sheet(tmp_path: Path) -> None:
    """The service passes bundle.canvas + bundle.anchor_sheet_name into the applier."""
    ctx    = _mock_ctx(tmp_path)
    bundle = SimpleNamespace(canvas=MagicMock(name="canvas"), anchor_sheet_name="TNA")
    plan   = SimpleNamespace(warnings=[])

    with patch("app.services.canvas_extract_v2_service.register_workbook", return_value=ctx), \
         patch("app.services.canvas_extract_v2_service.WorkbookPhase") as MockPhase, \
         patch("app.services.canvas_extract_v2_service.PlanAssembler") as MockPlanner, \
         patch("app.services.canvas_extract_v2_service.CanvasApplier") as MockApplier:
        MockPhase.return_value.run.return_value   = {"bundles": [bundle]}
        MockPlanner.return_value.run.return_value = {"plan": plan}
        MockApplier.return_value.run.return_value = {"plis": []}
        extract_canvas_v2(ctx.path)

    call_kwargs = MockApplier.return_value.run.call_args.kwargs
    assert call_kwargs["plan"]   is plan
    assert call_kwargs["canvas"] is bundle.canvas
    assert call_kwargs["sheet"]  == "TNA"
