"""Top-level orchestration for TNA workbook extraction.

This module owns the end-to-end extraction flow: classify relevant sheets,
build a `SheetPlan` per sheet via the SheetRowPlanner pipeline (surveyor +
row_classifier + kv_anchor_detector + stage_band_detector + block_segmenter),
validate the plan, conditionally invoke `LayoutHinter` and `PlanReviewer`,
name fields, apply the plan deterministically, and run cross-cutting
validators + reconciliation. Per-sheet failures are isolated from the
workbook-level extraction by the validators-and-reconciler stage.
"""
from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import structlog.contextvars

import app.repositories.workbook_tools.bulk_read  # noqa: F401
import app.repositories.workbook_tools.search  # noqa: F401
import app.repositories.workbook_tools.structure  # noqa: F401
import app.repositories.workbook_tools.survey  # noqa: F401
import app.repositories.workbook_tools.targeted  # noqa: F401
from app.core.logs import get_logger
from app.core.telemetry import (
    extraction_duration_seconds,
    extraction_phase_duration_seconds,
    extraction_pli_count,
    extractions_total,
    plis_extracted_total,
)
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import (
    CanonicalNameMap,
    LayoutHints,
    PlanVerdict,
    SheetPlan,
    ValidationFindings,
)
from app.models.extraction import ExtractionResult, PLI, Warning
from app.repositories.workbook_repo import register_workbook
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.services.agents.field_namer import FieldNamer
from app.components.layout_hinter import LayoutHinter
from app.services.agents.plan_reviewer import PlanReviewer
from app.components.sheet_classifier import SheetClassifier
from app.services.applier.apply_plan import apply_plan
from app.core.log_capture import log_artifact
from app.core.tracing import get_tracer
from app.services.llm_provider import AnthropicProvider
from app.services.planner.plan import SheetRowPlanner
from app.services.planner.surveyor import survey_sheet
from app.services.reconciler import reconcile
from app.services.validation.coverage_verifier import CoverageVerifier
from app.services.validation.field_dropout_verifier import FieldDropoutVerifier
from app.services.validation.header_match_verifier import HeaderMatchVerifier
from app.services.validation.plan_invariants import validate_invariants
from app.services.validation.plan_statistics import validate_statistics
from app.services.validation.source_cell_verifier import SourceCellVerifier

log = get_logger(__name__)

_CONFIDENCE_GATE = 0.85


@contextlib.contextmanager
def _phase(name: str, **attrs: Any) -> Iterator[Any]:
    """Time a phase + open an OTel span + bind phase to log context."""
    structlog.contextvars.bind_contextvars(phase=name)
    t0 = time.monotonic()
    with get_tracer(__name__).start_as_current_span(f"phase.{name}") as span:
        for k, v in attrs.items():
            try:
                span.set_attribute(k, v)
            except Exception:
                # best-effort: span attribute is telemetry-only, never block work
                pass
        try:
            yield span
        finally:
            extraction_phase_duration_seconds.record(time.monotonic() - t0, {"phase": name})
            structlog.contextvars.unbind_contextvars("phase")


def _snapshot_artifact(name: str, *, payload: Any) -> None:
    """Emit one structured log carrying a between-phase artifact snapshot."""
    log_artifact(name, payload=payload)


def _run_planner(ctx: Any, sheet: str) -> SheetPlan:
    """Run the deterministic SheetRowPlanner pipeline and return the plan."""
    planner = SheetRowPlanner()
    with _phase("planner"):
        plan: SheetPlan = planner.run(workbook_ctx=ctx, sheet=sheet)["plan"]
    log.info("plan_emitted",
             sheet=sheet, pli_mode=plan.pli_mode.value,
             confidence=plan.confidence,
             anchor_count=len([r for r in plan.rows if r.role.value == "anchor"]),
             block_count=len(plan.pli_blocks),
             kv_count=len(plan.kv_anchors),
             band_count=len(plan.stage_bands))
    return plan


def _validate_plan(ctx: Any, plan: SheetPlan, sheet: str) -> tuple[list, list, list]:
    """Run tier-1 invariants + tier-2 statistics; return (all, errors, warns)."""
    with _phase("plan_validate"):
        findings_t1 = validate_invariants(plan)
        findings_t2 = validate_statistics(ctx, plan)
        findings = findings_t1 + findings_t2
        errors = [f for f in findings if f.severity == ValidationSeverity.ERROR]
        warns = [f for f in findings if f.severity == ValidationSeverity.WARN]
    log.info("plan_validation_complete", sheet=sheet,
             tier1_errors=sum(1 for f in findings_t1 if f.severity == ValidationSeverity.ERROR),
             tier1_warns=sum(1 for f in findings_t1 if f.severity == ValidationSeverity.WARN),
             tier2_warns=len(findings_t2))
    return findings, errors, warns


def _apply_layout_hints_if_needed(
    ctx: Any, sheet: str, plan: SheetPlan, errors: list, llm: Any, warnings: list[Warning],
) -> SheetPlan:
    """Call LayoutHinter when tier-1 validation has errors; possibly update plan."""
    if not errors:
        return plan
    log.info("layout_hinter_invoked", sheet=sheet, identity_suggestion=None)
    hinter = LayoutHinter(llm=llm)
    signals = survey_sheet(ctx, sheet)
    hints: LayoutHints = hinter.run(
        workbook_ctx=ctx, sheet=sheet, signals=signals,
    )["hints"]
    log.info("layout_hinter_invoked", sheet=sheet,
             identity_suggestion=hints.identity_column_suggestion)
    if hints.identity_column_suggestion:
        plan = plan.model_copy(update={"identity_column": hints.identity_column_suggestion})
    findings_t1 = validate_invariants(plan)
    findings_t2 = validate_statistics(ctx, plan)
    for f in findings_t1 + findings_t2:
        warnings.append(Warning(message=f"{f.check}: {f.message}", severity="warning"))
    return plan


def _apply_plan_review_if_needed(
    ctx: Any, sheet: str, plan: SheetPlan, findings: list, warns: list, llm: Any,
) -> SheetPlan:
    """Call PlanReviewer on warnings, low confidence, or non-row mode; apply fixes."""
    needs_reviewer = (
        bool(warns)
        or plan.confidence < _CONFIDENCE_GATE
        or plan.pli_mode is not PliMode.ROW_PER_PLI
    )
    if not needs_reviewer:
        return plan
    log.info("plan_reviewer_invoked", sheet=sheet,
             reason="warnings" if warns else "low_confidence" if plan.confidence < _CONFIDENCE_GATE else "non_row_mode")
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
                    suggested = corr.get("suggested_role", r.role)
                    # Coerce string role values from LLM JSON responses to RowRole enum.
                    if isinstance(suggested, str):
                        try:
                            suggested = RowRole(suggested)
                        except ValueError:
                            suggested = r.role
                    new_rows[i] = r.model_copy(update={
                        "role": suggested,
                        "anchor_idx": corr.get("anchor_idx", r.anchor_idx),
                    })
                    break
        plan = plan.model_copy(update={"rows": new_rows})
    return plan


def _plan_for_sheet(
    ctx: Any, sheet: str, llm: Any,
) -> tuple[SheetPlan, CanonicalNameMap, list[Warning]]:
    """Plan one sheet: run planner, validate, optionally refine, name fields."""
    warnings: list[Warning] = []

    plan = _run_planner(ctx, sheet)
    _snapshot_artifact("plan.snapshot_after_planner", payload=plan.model_dump())
    findings, errors, warns = _validate_plan(ctx, plan, sheet)
    plan = _apply_layout_hints_if_needed(ctx, sheet, plan, errors, llm, warnings)
    plan = _apply_plan_review_if_needed(ctx, sheet, plan, findings, warns, llm)
    _snapshot_artifact("plan.snapshot_after_reviewer", payload=plan.model_dump())

    with _phase("field_namer"):
        namer = FieldNamer(llm=llm)
        name_map: CanonicalNameMap = namer.run(workbook_ctx=ctx, plan=plan)["name_map"]
    _snapshot_artifact("name_map.snapshot_after_namer", payload=name_map.model_dump())
    log.info("name_map_received", sheet=sheet,
             field_count=len(name_map.field_labels),
             stage_count=len(name_map.stage_names))

    return plan, name_map, warnings


def extract(workbook_path: Path | str, *, llm: Any = None) -> ExtractionResult:
    """Extract structured PLIs from a TNA workbook, end-to-end."""
    t0 = time.monotonic()
    ctx = register_workbook(workbook_path)
    llm = llm or AnthropicProvider.from_env()

    log.info("extract_start", file=str(ctx.path))
    with get_tracer(__name__).start_as_current_span("extract") as root_span:
        root_span.set_attribute("file", str(ctx.path))
        try:
            with _phase("sheet_classifier"):
                summary = TOOL_REGISTRY.get("workbook_summary")(ctx)
                sc = SheetClassifier(llm=llm)
                relevant = sc.run(workbook_ctx=ctx, workbook_summary=summary)["relevant_sheets"]
            if not relevant:
                log.info("no_relevant_sheets", file=str(ctx.path))
                extractions_total.add(1, {"status": "empty"})
                return ExtractionResult(
                    plis=[], source_file=str(ctx.path),
                    warnings=[Warning(message="No relevant sheets identified", severity="warning")],
                )

            log.info("relevant_sheets_selected", sheets=relevant, count=len(relevant))
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
                log.info("plis_emitted", sheet=sheet, pli_count=len(plis))
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
            log.info("extract_complete", file=ctx.path.name, total_plis=len(final.plis),
                     warnings=len(final.warnings), format=final.format_detected)
            extraction_duration_seconds.record(
                time.monotonic() - t0,
                {"format_detected": final.format_detected or "unknown"},
            )
            extraction_pli_count.add(
                len(final.plis), {"source_file": ctx.path.name}
            )
            if len(final.plis) == 0:
                extractions_total.add(1, {"status": "empty"})
            else:
                extractions_total.add(1, {"status": "success"})
            plis_extracted_total.add(len(final.plis))
            return final
        except Exception:
            # log+re-raise: count the failure for observability, surface to caller
            extractions_total.add(1, {"status": "failure"})
            raise
