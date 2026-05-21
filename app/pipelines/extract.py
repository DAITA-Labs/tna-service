"""Haystack Pipeline factories for TNA workbook extraction.

Two factories:
- `make_per_sheet_pipeline(llm)` — builds the per-sheet processing DAG
- `make_extract_pipeline(llm, ctx)` — builds the workbook-level DAG

Orchestration (provider init, telemetry, empty-sheet guard) lives in
`app/services/extract_service.py`. These factories are pure DAG construction:
no side effects, no provider init, no telemetry.
"""
from __future__ import annotations

from typing import Any

from haystack import Pipeline

from app.components.per_sheet.applier import Applier
from app.components.per_sheet.field_namer import FieldNamer
from app.components.per_sheet.layout_hinter import LayoutHinter
from app.components.per_sheet.plan_reviewer import PlanReviewer
from app.components.per_sheet.plan_validator import PlanValidator
from app.components.per_sheet.planner import Planner
from app.components.validators.coverage_verifier import CoverageVerifier
from app.components.validators.field_dropout_verifier import FieldDropoutVerifier
from app.components.validators.header_match_verifier import HeaderMatchVerifier
from app.components.validators.post_namer_validator import PostNamerValidator
from app.components.validators.post_review_validator import PostReviewValidator
from app.components.validators.pre_apply_validator import PreApplyValidator
from app.components.validators.source_cell_verifier import SourceCellVerifier
from app.components.workbook.extraction_result_builder import ExtractionResultBuilder
from app.components.workbook.per_sheet import PerSheetProcessor
from app.components.workbook.reconciler import Reconciler
from app.components.workbook.sheet_classifier import SheetClassifier
from app.components.workbook.summary_provider import WorkbookSummaryProvider


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
