"""Top-level orchestration for TNA workbook extraction.

Provides two Haystack Pipeline factories:
- `make_per_sheet_pipeline(llm)` — builds the per-sheet flow DAG
- `make_extract_pipeline(llm)` — builds the workbook-level DAG

The thin `extract()` driver registers the workbook, handles the empty-sheet
early-return, then runs the pipeline and returns the reconciled result.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import app.tools.bulk_read  # noqa: F401 — force tool registration
import app.tools.search  # noqa: F401
import app.tools.structure  # noqa: F401
import app.tools.survey  # noqa: F401
import app.tools.targeted  # noqa: F401
from haystack import Pipeline

from app.components.applier import Applier
from app.components.extraction_result_builder import ExtractionResultBuilder
from app.components.field_namer import FieldNamer
from app.components.layout_hinter import LayoutHinter
from app.components.per_sheet import PerSheetProcessor
from app.components.plan_reviewer import PlanReviewer
from app.components.plan_validator import PlanValidator
from app.components.planner_component import Planner
from app.components.post_namer_validator import PostNamerValidator
from app.components.post_review_validator import PostReviewValidator
from app.components.pre_apply_validator import PreApplyValidator
from app.components.reconciler import Reconciler
from app.components.sheet_classifier import SheetClassifier
from app.components.validators.coverage_verifier import CoverageVerifier
from app.components.validators.field_dropout_verifier import FieldDropoutVerifier
from app.components.validators.header_match_verifier import HeaderMatchVerifier
from app.components.validators.source_cell_verifier import SourceCellVerifier
from app.components.workbook_summary_provider import WorkbookSummaryProvider
from app.core.logs import get_logger
from app.core.telemetry import (
    extraction_duration_seconds,
    extraction_pli_count,
    extractions_total,
    plis_extracted_total,
)
from app.core.tracing import get_tracer
from app.models.extraction import ExtractionResult, Warning
from app.repositories.workbook_repo import register_workbook
from app.services.llm_provider import AnthropicProvider
from app.tools._registry import TOOL_REGISTRY

log = get_logger(__name__)


def make_per_sheet_pipeline(llm: Any) -> Pipeline:
    """Build the per-sheet processing pipeline.

    DAG: planner → plan_validator → layout_hinter → plan_reviewer →
         post_review_validator → field_namer → post_namer_validator →
         pre_apply_validator → applier
    """
    pipe = Pipeline()
    pipe.add_component("planner", Planner())
    pipe.add_component("plan_validator", PlanValidator())
    pipe.add_component("layout_hinter", LayoutHinter(llm=llm))
    pipe.add_component("plan_reviewer", PlanReviewer(llm=llm))
    pipe.add_component("post_review_validator", PostReviewValidator())
    pipe.add_component("field_namer", FieldNamer(llm=llm))
    pipe.add_component("post_namer_validator", PostNamerValidator())
    pipe.add_component("pre_apply_validator", PreApplyValidator())
    pipe.add_component("applier", Applier())

    # planner → plan_validator
    pipe.connect("planner.plan", "plan_validator.plan")
    # plan_validator → layout_hinter
    pipe.connect("plan_validator.plan", "layout_hinter.plan")
    pipe.connect("plan_validator.findings", "layout_hinter.findings")
    # layout_hinter → plan_reviewer
    pipe.connect("layout_hinter.plan", "plan_reviewer.plan")
    pipe.connect("plan_validator.findings", "plan_reviewer.findings")
    # plan_reviewer → post_review_validator
    pipe.connect("plan_reviewer.plan", "post_review_validator.plan")
    # post_review_validator → field_namer
    pipe.connect("post_review_validator.plan", "field_namer.plan")
    # field_namer → post_namer_validator
    pipe.connect("field_namer.name_map", "post_namer_validator.name_map")
    pipe.connect("post_review_validator.plan", "post_namer_validator.plan")
    # post_review_validator → pre_apply_validator
    pipe.connect("post_review_validator.plan", "pre_apply_validator.plan")
    # pre_apply_validator → applier
    pipe.connect("pre_apply_validator.plan", "applier.plan")
    pipe.connect("pre_apply_validator.findings", "applier.findings_pre_apply")
    # post_namer_validator → applier
    pipe.connect("post_namer_validator.name_map", "applier.name_map")

    return pipe


def make_extract_pipeline(llm: Any, ctx: Any) -> Pipeline:
    """Build the workbook-level extract pipeline.

    DAG: summary_provider → sheet_classifier → per_sheet →
         result_builder → [4 verifiers] → reconciler
    """
    pipe = Pipeline()
    pipe.add_component("summary_provider", WorkbookSummaryProvider())
    pipe.add_component("sheet_classifier", SheetClassifier(llm=llm))
    pipe.add_component("per_sheet", PerSheetProcessor(llm=llm))
    pipe.add_component("result_builder", ExtractionResultBuilder())
    pipe.add_component("source_cell", SourceCellVerifier(workbook_ctx=ctx))
    pipe.add_component("header_match", HeaderMatchVerifier(workbook_ctx=ctx))
    pipe.add_component("coverage", CoverageVerifier(boundaries=[]))
    pipe.add_component("field_dropout", FieldDropoutVerifier())
    pipe.add_component("reconciler", Reconciler())

    pipe.connect("summary_provider.summary", "sheet_classifier.workbook_summary")
    pipe.connect("sheet_classifier.relevant_sheets", "per_sheet.relevant_sheets")
    pipe.connect("per_sheet.plis", "result_builder.plis")
    pipe.connect("per_sheet.warnings", "result_builder.warnings")
    pipe.connect("per_sheet.format_detected", "result_builder.format_detected")
    pipe.connect("result_builder.result", "source_cell.extraction")
    pipe.connect("result_builder.result", "header_match.extraction")
    pipe.connect("result_builder.result", "coverage.extraction")
    pipe.connect("result_builder.result", "field_dropout.extraction")
    pipe.connect("result_builder.result", "reconciler.workflow_out")
    pipe.connect("source_cell.findings", "reconciler.source_findings")
    pipe.connect("header_match.findings", "reconciler.header_findings")
    pipe.connect("coverage.findings", "reconciler.coverage_findings")
    pipe.connect("field_dropout.findings", "reconciler.dropout_findings")

    return pipe


def extract(workbook_path: Path | str, *, llm: Any = None) -> ExtractionResult:
    """Extract structured PLIs from a TNA workbook via the Haystack Pipeline."""
    t0 = time.monotonic()
    ctx = register_workbook(workbook_path)
    llm = llm or AnthropicProvider.from_env()

    log.info("extract_start", file=str(ctx.path))
    with get_tracer(__name__).start_as_current_span("extract") as root_span:
        root_span.set_attribute("file", str(ctx.path))
        try:
            # Early-return when no relevant sheets — avoids building the full pipeline.
            summary = TOOL_REGISTRY.get("workbook_summary")(ctx)
            sc = SheetClassifier(llm=llm)
            relevant = sc.run(workbook_ctx=ctx, workbook_summary=summary)["relevant_sheets"]
            if not relevant:
                log.info("no_relevant_sheets", file=str(ctx.path))
                extractions_total.add(1, {"status": "empty"})
                return ExtractionResult(
                    plis=[], source_file=str(ctx.path),
                    warnings=[Warning(
                        message="No relevant sheets identified", severity="warning",
                    )],
                )

            log.info("relevant_sheets_selected", sheets=relevant, count=len(relevant))
            pipe = make_extract_pipeline(llm, ctx)
            out = pipe.run({
                "summary_provider": {"workbook_ctx": ctx},
                "sheet_classifier": {"workbook_ctx": ctx},
                "per_sheet": {"workbook_ctx": ctx},
                "result_builder": {"source_file": str(ctx.path)},
            })
            final: ExtractionResult = out["reconciler"]["result"]
            log.info(
                "extract_complete",
                file=ctx.path.name,
                total_plis=len(final.plis),
                warnings=len(final.warnings),
                format=final.format_detected,
            )
            extraction_duration_seconds.record(
                time.monotonic() - t0,
                {"format_detected": final.format_detected or "unknown"},
            )
            extraction_pli_count.add(len(final.plis), {"source_file": ctx.path.name})
            if len(final.plis) == 0:
                extractions_total.add(1, {"status": "empty"})
            else:
                extractions_total.add(1, {"status": "success"})
            plis_extracted_total.add(len(final.plis))
            return final
        except Exception:
            extractions_total.add(1, {"status": "failure"})
            raise
