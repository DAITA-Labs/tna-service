"""Orchestration service for TNA workbook extraction.

Initialises the LLM provider, builds the Haystack Pipeline via the
factories in app/pipelines/extract.py, assembles the input dict,
runs the pipeline, and returns the structured result. The HTTP
router (app/routers/extract.py) is the only caller.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import app.tools.bulk_read  # noqa: F401 — force tool registration before pipeline build
import app.tools.search  # noqa: F401
import app.tools.structure  # noqa: F401
import app.tools.survey  # noqa: F401
import app.tools.targeted  # noqa: F401
from app.components.workbook.sheet_classifier import SheetClassifier
from app.core.logs import get_logger
from app.core.telemetry import (
    extraction_duration_seconds,
    extraction_pli_count,
    extractions_total,
    plis_extracted_total,
)
from app.core.tracing import get_tracer
from app.inferencing.anthropic import AnthropicProvider
from app.models.extraction import ExtractionResult, Warning
from app.pipelines.extract import make_extract_pipeline
from app.repositories.workbook_repo import register_workbook
from app.tools._registry import TOOL_REGISTRY

log = get_logger(__name__)


def extract(workbook_path: Path | str, *, llm: Any = None) -> ExtractionResult:
    """Extract structured PLIs from a TNA workbook via the Haystack Pipeline."""
    t0 = time.monotonic()
    ctx = register_workbook(workbook_path)
    llm = llm or AnthropicProvider.from_env()

    log.info("extract_start", file=str(ctx.path))
    with get_tracer(__name__).start_as_current_span("extract") as root_span:
        root_span.set_attribute("file", str(ctx.path))
        try:
            return _run_pipeline(ctx, llm, t0)
        except Exception:
            extractions_total.add(1, {"status": "failure"})
            raise


def _run_pipeline(ctx: Any, llm: Any, t0: float) -> ExtractionResult:
    """Build the workbook pipeline, run it, and return the final result.

    Performs the empty-sheets early-return before building the full pipeline,
    to avoid unnecessary component initialisation.
    """
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
    _record_telemetry(final, ctx, t0)
    return final


def _record_telemetry(final: ExtractionResult, ctx: Any, t0: float) -> None:
    """Emit duration, PLI count, and status metrics for one extraction."""
    log.info(
        "extract_complete",
        file=ctx.path.name, total_plis=len(final.plis),
        warnings=len(final.warnings), format=final.format_detected,
    )
    extraction_duration_seconds.record(
        time.monotonic() - t0,
        {"format_detected": final.format_detected or "unknown"},
    )
    extraction_pli_count.add(len(final.plis), {"source_file": ctx.path.name})
    status = "success" if final.plis else "empty"
    extractions_total.add(1, {"status": status})
    plis_extracted_total.add(len(final.plis))
