"""Plan-driven canvas extraction service — `/extract_canvas_plan` orchestration.

Parallel to the legacy `/extract` planner service. Runs the
plan-driven chain end-to-end:

  1. `WorkbookPhase`              — workbook → list[ClusterAnchorBundle]
  2. `PlanAssembler`              — bundle → CanvasPlan          (per bundle)
  3. `CanvasPlanReviewerGate`     — plan → plan' (LLM review only when
                                      warnings or low confidence fire)
  4. `CanvasApplier`              — plan' + canvas → list[PLI]   (per bundle)

Per-bundle outputs merge into one `ExtractionResult`.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.artifacts.finding import ValidationWarning
from app.components.judges.canvas_plan_reviewer_gate import CanvasPlanReviewerGate
from app.components.plan import CanvasApplier, PlanAssembler
from app.components.workbook.workbook_phase import WorkbookPhase
from app.core.logs import get_logger
from app.core.telemetry import (
    extraction_duration_seconds,
    extraction_pli_count,
    extractions_total,
    plis_extracted_total,
)
from app.core.tracing import get_tracer
from app.inferencing._base import BaseProvider
from app.inferencing.factory import build_provider
from app.models.extraction import ExtractionResult, PLI, Warning
from app.repositories import register_workbook


log = get_logger(__name__)

_PATH_LABEL = "canvas_plan"


def extract_canvas_plan(
    workbook_path: Path | str, *, llm: BaseProvider | None = None,
) -> ExtractionResult:
    """Run the plan-driven canvas extraction chain end-to-end."""
    t0  = time.monotonic()
    ctx = register_workbook(workbook_path)
    llm = llm or build_provider()

    log.info("canvas_plan_extract_start", file=str(ctx.path))
    with get_tracer(__name__).start_as_current_span("canvas_extract_plan") as root_span:
        root_span.set_attribute("file", str(ctx.path))
        try:
            result = _run_chain(ctx, llm)
        except Exception:
            extractions_total.add(1, {"status": "failure", "path": _PATH_LABEL})
            raise

    _record_telemetry(result, ctx, t0)
    return result


def _run_chain(ctx: Any, llm: BaseProvider) -> ExtractionResult:
    """Drive WorkbookPhase → (PlanAssembler → ReviewerGate → CanvasApplier) per bundle."""
    bundles = WorkbookPhase().run(workbook=ctx.wb)["bundles"]
    if not bundles:
        log.info("canvas_plan_no_pli_clusters", file=str(ctx.path))
        extractions_total.add(1, {"status": "empty", "path": _PATH_LABEL})
        return ExtractionResult(
            plis=[], source_file=str(ctx.path),
            warnings=[Warning(
                message="No PLI clusters detected", severity="warning",
            )],
        )

    planner       = PlanAssembler()
    reviewer_gate = CanvasPlanReviewerGate(llm=llm)
    applier       = CanvasApplier()

    all_plis:     list[PLI]     = []
    all_warnings: list[Warning] = []
    for bundle in bundles:
        plan = planner.run(bundle=bundle)["plan"]
        plan = reviewer_gate.run(plan=plan, bundle=bundle)["plan"]
        plis = applier.run(
            plan=plan, canvas=bundle.canvas, sheet=bundle.anchor_sheet_name,
        )["plis"]
        all_plis.extend(plis)
        all_warnings.extend(_warning_to_public(w) for w in plan.warnings)

    return ExtractionResult(
        plis=all_plis,
        warnings=all_warnings,
        source_file=str(ctx.path),
    )


def _warning_to_public(w: ValidationWarning) -> Warning:
    return Warning(message=w.message, severity=w.severity, check=w.name)


def _record_telemetry(result: ExtractionResult, ctx: Any, t0: float) -> None:
    elapsed   = time.monotonic() - t0
    pli_count = len(result.plis)
    extraction_duration_seconds.record(elapsed, {"path": _PATH_LABEL})
    extraction_pli_count.add(pli_count,       {"path": _PATH_LABEL})
    plis_extracted_total.add(pli_count,       {"path": _PATH_LABEL})
    extractions_total.add(1, {"status": "success", "path": _PATH_LABEL})
    log.info(
        "canvas_plan_extract_complete",
        file=str(ctx.path),
        elapsed_seconds=elapsed,
        pli_count=pli_count,
        warning_count=len(result.warnings),
    )
