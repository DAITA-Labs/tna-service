"""Top-level orchestration with the new SheetRowPlanner-based pipeline."""
from __future__ import annotations
import contextlib
import time
from pathlib import Path
import structlog.contextvars
from app.repositories.workbook_repo import register_workbook
from app.models.extraction import ExtractionResult, PLI, Warning
from app.models.artifacts import (
    SheetPlan, CanonicalNameMap, LayoutHints, PlanVerdict, ValidationFindings,
)
from app.enums.pli_mode import PliMode
from app.enums.validation_severity import ValidationSeverity
from app.services.llm_provider import AnthropicProvider
from app.services.agents.sheet_classifier import SheetClassifier
from app.services.agents.layout_hinter import LayoutHinter
from app.services.agents.plan_reviewer import PlanReviewer
from app.services.agents.field_namer import FieldNamer
from app.services.planner.plan import SheetRowPlanner
from app.services.planner.surveyor import survey_sheet
from app.services.validation.plan_invariants import validate_invariants
from app.services.validation.plan_statistics import validate_statistics
from app.services.applier.apply_plan import apply_plan
from app.services.validation.source_cell_verifier import SourceCellVerifier
from app.services.validation.header_match_verifier import HeaderMatchVerifier
from app.services.validation.coverage_verifier import CoverageVerifier
from app.services.validation.field_dropout_verifier import FieldDropoutVerifier
from app.services.reconciler import reconcile
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.core.logs import get_logger
from app.core.telemetry import (
    extraction_duration_seconds,
    extraction_pli_count,
    extraction_phase_duration_seconds,
    extractions_total,
)
import app.repositories.workbook_tools.survey  # noqa: F401
import app.repositories.workbook_tools.bulk_read  # noqa: F401
import app.repositories.workbook_tools.targeted  # noqa: F401
import app.repositories.workbook_tools.structure  # noqa: F401
import app.repositories.workbook_tools.search  # noqa: F401

log = get_logger(__name__)


@contextlib.contextmanager
def _phase(name: str):
    """Time a named phase and bind it to the structlog context."""
    structlog.contextvars.bind_contextvars(phase=name)
    t0 = time.monotonic()
    try:
        yield
    finally:
        extraction_phase_duration_seconds.labels(phase=name).observe(
            time.monotonic() - t0
        )
        structlog.contextvars.unbind_contextvars("phase")

_CONFIDENCE_GATE = 0.85


def _plan_for_sheet(ctx, sheet: str, llm):
    warnings: list[Warning] = []
    planner = SheetRowPlanner()

    with _phase("planner"):
        plan: SheetPlan = planner.run(workbook_ctx=ctx, sheet=sheet)["plan"]

    with _phase("plan_validate"):
        findings_t1 = validate_invariants(plan)
        findings_t2 = validate_statistics(ctx, plan)
        findings = findings_t1 + findings_t2
        errors = [f for f in findings if f.severity == ValidationSeverity.ERROR]
        warns = [f for f in findings if f.severity == ValidationSeverity.WARN]

    needs_reviewer = (
        bool(warns)
        or plan.confidence < _CONFIDENCE_GATE
        or plan.pli_mode is not PliMode.ROW_PER_PLI
    )

    if errors:
        hinter = LayoutHinter(llm=llm)
        signals = survey_sheet(ctx, sheet)
        hints: LayoutHints = hinter.run(
            workbook_ctx=ctx, sheet=sheet, signals=signals,
        )["hints"]
        if hints.identity_column_suggestion:
            plan = plan.model_copy(update={"identity_column": hints.identity_column_suggestion})
        findings_t1 = validate_invariants(plan)
        findings_t2 = validate_statistics(ctx, plan)
        for f in findings_t1 + findings_t2:
            warnings.append(Warning(message=f"{f.check}: {f.message}", severity="warning"))

    if needs_reviewer:
        with _phase("plan_reviewer"):
            reviewer = PlanReviewer(llm=llm)
            verdict: PlanVerdict = reviewer.run(
                workbook_ctx=ctx, plan=plan, findings=findings,
            )["verdict"]
        if verdict.verdict == "needs_fix":
            new_rows = list(plan.rows)
            for corr in verdict.row_corrections:
                for i, r in enumerate(new_rows):
                    if r.idx == corr.get("row"):
                        new_rows[i] = r.model_copy(update={
                            "role": corr.get("suggested_role", r.role),
                            "anchor_idx": corr.get("anchor_idx", r.anchor_idx),
                        })
                        break
            plan = plan.model_copy(update={"rows": new_rows})

    with _phase("field_namer"):
        namer = FieldNamer(llm=llm)
        name_map: CanonicalNameMap = namer.run(workbook_ctx=ctx, plan=plan)["name_map"]

    return plan, name_map, warnings


def extract(workbook_path: Path | str, *, llm=None) -> ExtractionResult:
    t0 = time.monotonic()
    ctx = register_workbook(workbook_path)
    llm = llm or AnthropicProvider.from_env()

    try:
        with _phase("sheet_classifier"):
            summary = TOOL_REGISTRY.get("workbook_summary")(ctx)
            sc = SheetClassifier(llm=llm)
            relevant = sc.run(workbook_ctx=ctx, workbook_summary=summary)["relevant_sheets"]
        if not relevant:
            extractions_total.labels(status="empty").inc()
            return ExtractionResult(
                plis=[], source_file=str(ctx.path),
                warnings=[Warning(message="No relevant sheets identified", severity="warning")],
            )

        all_plis: list[PLI] = []
        all_warnings: list[Warning] = []
        format_detected: str | None = None

        for sheet in relevant:
            plan, name_map, warns = _plan_for_sheet(ctx, sheet, llm)
            all_warnings.extend(warns)
            with _phase("apply_plan"):
                plis = apply_plan(ctx, plan, name_map)
            for pli in plis:
                if not pli.source.sheet:
                    pli.source.sheet = sheet
            all_plis.extend(plis)
            if format_detected is None:
                format_detected = plan.pli_mode.value

        result = ExtractionResult(
            plis=all_plis, warnings=all_warnings,
            format_detected=format_detected, source_file=str(ctx.path),
        )
        with _phase("validators"):
            src_v = SourceCellVerifier(workbook_ctx=ctx).run(extraction=result)["findings"]
            hdr_v = HeaderMatchVerifier(workbook_ctx=ctx).run(extraction=result)["findings"]
            cov_v = CoverageVerifier(boundaries=[]).run(extraction=result)["findings"]
            drop_v = FieldDropoutVerifier().run(extraction=result)["findings"]
        all_findings = ValidationFindings(findings=(
            src_v.findings + hdr_v.findings + cov_v.findings + drop_v.findings
        ))
        with _phase("reconciler"):
            final = reconcile(workflow_out=result, validation_out=all_findings)
        extraction_duration_seconds.labels(
            format_detected=final.format_detected or "unknown"
        ).observe(time.monotonic() - t0)
        extraction_pli_count.labels(source_file=ctx.path.name).set(len(final.plis))
        if len(final.plis) == 0:
            extractions_total.labels(status="empty").inc()
        else:
            extractions_total.labels(status="success").inc()
        return final
    except Exception:
        extractions_total.labels(status="failure").inc()
        raise
