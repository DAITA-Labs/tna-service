"""Canvas-architecture extraction service — `/extract_canvas` orchestration.

Parallel to the legacy `extract` service in this same package. Runs the
five canvas pipelines in order at the service layer (option B from the
Tier 6 design discussion):

  1. `WorkbookPhase`              — workbook → list[ClusterAnchorBundle]
  2. `make_canvas_extract_pipeline()` — per-bundle: deterministic field
                                      extractors + arbiter + stages + metadata
  3. `make_canvas_validators_pipeline()` — per-bundle structural warnings
  4. `make_canvas_judges_pipeline(llm)` — per-bundle LLM adjudication
  5. `CanvasReconciler`           — per-bundle ExtractionResult assembly

Per-bundle results merge into one `ExtractionResult` at the end. The
service is the only thing that knows the chain; each pipeline is a
self-contained DAG with no awareness of the others.

`extract_canvas(path)` is the public entry point; the `/extract_canvas`
router calls it. The legacy `/extract` route stays untouched.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import app.tools.bulk_read  # noqa: F401 — register tools before pipeline build
import app.tools.search  # noqa: F401
import app.tools.structure  # noqa: F401
import app.tools.survey  # noqa: F401
import app.tools.targeted  # noqa: F401
from app.artifacts.finding import Finding, ValidationWarning
from app.artifacts.workbook import ClusterAnchorBundle
from app.components.workbook.canvas_reconciler import CanvasReconciler
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
from app.models.extraction import ExtractionResult, Warning
from app.repositories import register_workbook
from app.pipelines.canvas_extract import make_canvas_extract_pipeline
from app.pipelines.canvas_judges import make_canvas_judges_pipeline
from app.pipelines.canvas_validators import make_canvas_validators_pipeline
from app.specs.schemas import FinalStage, MetadataEntry


log = get_logger(__name__)


_PER_CANONICAL_INPUT_KEYS: tuple[str, ...] = (
    "io_number", "quantity", "style_code", "color_code", "fabric_code",
    "style_name", "color_name", "fabric_name",
    "delivery_date", "shipment_date", "ex_fty_date",
)


def extract_canvas(
    workbook_path: Path | str, *, llm: BaseProvider | None = None,
) -> ExtractionResult:
    """Run the canvas-architecture extraction chain end-to-end."""
    t0 = time.monotonic()
    ctx = register_workbook(workbook_path)
    llm = llm or build_provider()

    log.info("canvas_extract_start", file=str(ctx.path))
    with get_tracer(__name__).start_as_current_span("canvas_extract") as root_span:
        root_span.set_attribute("file", str(ctx.path))
        try:
            result = _run_chain(ctx, llm)
        except Exception:
            extractions_total.add(1, {"status": "failure", "path": "canvas"})
            raise

    _record_telemetry(result, ctx, t0)
    return result


def _run_chain(ctx: Any, llm: BaseProvider) -> ExtractionResult:
    """Drive the five-pipeline chain, one bundle at a time, and merge."""
    bundles = WorkbookPhase().run(workbook=ctx.wb)["bundles"]
    if not bundles:
        log.info("canvas_no_pli_clusters", file=str(ctx.path))
        extractions_total.add(1, {"status": "empty", "path": "canvas"})
        return ExtractionResult(
            plis=[], source_file=str(ctx.path),
            warnings=[Warning(
                message="No PLI clusters detected", severity="warning",
            )],
        )

    extract_pipeline    = make_canvas_extract_pipeline()
    validators_pipeline = make_canvas_validators_pipeline()
    judges_pipeline     = make_canvas_judges_pipeline(llm)
    reconciler          = CanvasReconciler()

    all_plis = []
    all_warnings = []
    for bundle in bundles:
        findings, stages, metadata = _run_extraction(extract_pipeline, bundle)
        warnings = _run_validators(validators_pipeline, findings, stages, bundle)
        final = _run_judges(
            judges_pipeline,
            raw_findings=findings,
            raw_stages=stages,
            metadata_entries=metadata,
            warnings=warnings,
            bundle=bundle,
        )
        per_bundle = reconciler.run(
            findings=final["findings"],
            stages_per_row=final["stages_per_row"],
            metadata=final["metadata_entries"],
            warnings=warnings,
            source_file=str(ctx.path),
            sheet=bundle.anchor_sheet_name,
        )["result"]
        all_plis.extend(per_bundle.plis)
        all_warnings.extend(per_bundle.warnings)

    return ExtractionResult(
        plis=all_plis,
        warnings=all_warnings,
        source_file=str(ctx.path),
    )


# ── per-bundle stage runners ───────────────────────────────────────────


def _run_extraction(pipeline, bundle: ClusterAnchorBundle):
    """Per-canonical extractors + arbiter + stages + metadata for one bundle."""
    inputs = {name: {"bundle": bundle} for name in _PER_CANONICAL_INPUT_KEYS}
    inputs["stages"]   = {"bundle": bundle}
    inputs["metadata"] = {"bundle": bundle}
    out = pipeline.run(inputs)
    findings: list[Finding]                    = out["arbiter"]["findings"]
    stages:   dict[int, list[FinalStage]]      = out["stages"]["stages_per_row"]
    metadata: list[MetadataEntry]              = out["metadata"]["metadata"]
    return findings, stages, metadata


def _run_validators(
    pipeline,
    findings: list[Finding],
    stages: dict[int, list[FinalStage]],
    bundle: ClusterAnchorBundle,
) -> list[ValidationWarning]:
    """Run the canvas validators pipeline for one bundle."""
    out = pipeline.run({
        "cardinality":     {"findings": findings, "bundle": bundle},
        "row_alignment":   {"findings": findings, "bundle": bundle},
        "date_trio":       {"findings": findings, "bundle": bundle},
        "stage_wins":      {"findings": findings, "bundle": bundle},
        "stage_structure": {"bundle": bundle},
        "quantity_dtype":  {"findings": findings, "bundle": bundle},
        "stage_sequence":  {"stages_per_row": stages},
    })
    return out["aggregator"]["warnings"]


def _run_judges(
    pipeline,
    *,
    raw_findings: list[Finding],
    raw_stages: dict[int, list[FinalStage]],
    metadata_entries: list[MetadataEntry],
    warnings: list[ValidationWarning],
    bundle: ClusterAnchorBundle,
) -> dict[str, Any]:
    """Run the canvas judges pipeline for one bundle.

    Returns a dict with `findings`, `stages_per_row`, and `metadata_entries`
    keys — the post-judging final outputs ready for reconciliation.
    """
    out = pipeline.run({
        "identifier_finding": {"findings": raw_findings, "warnings": warnings, "bundle": bundle},
        "identifier_phase":   {"raw_findings": raw_findings, "warnings": warnings, "bundle": bundle},
        "stage_finding":      {"stages_per_row": raw_stages, "bundle": bundle},
        "stage_phase":        {"raw_stages_per_row": raw_stages, "warnings": warnings, "bundle": bundle},
        "metadata":           {"metadata_entries": metadata_entries, "bundle": bundle},
    })
    return {
        "findings":         out["identifier_phase"]["findings"],
        "stages_per_row":   out["stage_phase"]["stages_per_row"],
        "metadata_entries": out["metadata"]["metadata_entries"],
    }


def _record_telemetry(final: ExtractionResult, ctx: Any, t0: float) -> None:
    """Emit duration, PLI count, and status metrics for one canvas extraction."""
    elapsed = time.monotonic() - t0
    pli_count = len(final.plis)
    extraction_duration_seconds.record(elapsed, {"path": "canvas"})
    extraction_pli_count.add(pli_count, {"path": "canvas"})
    plis_extracted_total.add(pli_count, {"path": "canvas"})
    extractions_total.add(1, {"status": "success", "path": "canvas"})
    log.info(
        "canvas_extract_complete",
        file=str(ctx.path),
        elapsed_seconds=elapsed,
        pli_count=pli_count,
        warning_count=len(final.warnings),
    )
