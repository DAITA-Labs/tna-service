"""POST /extract_canvas_v2 — upload xlsx, run plan-driven chain, return ExtractionResult.

Parallel to `POST /extract_canvas` (per-canonical extractors path) and
`POST /extract` (legacy planner path). This endpoint runs the
plan-driven canvas chain: `WorkbookPhase` → `PlanAssembler` →
`CanvasApplier`. Same response contract as the other routes; different
internals.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.logs import get_logger
from app.schemas.extract import ExtractResponse
from app.services.canvas_extract_v2_service import extract_canvas_v2


log    = get_logger(__name__)
router = APIRouter()


@router.post("/extract_canvas_v2", response_model=ExtractResponse, tags=["extract"])
async def extract_canvas_v2_endpoint(file: UploadFile) -> ExtractResponse:
    """Extract structured PLI / Stage JSON via the plan-driven canvas chain."""
    log.info("extract_canvas_v2_request_received", filename=file.filename,
             content_type=file.content_type)
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="expected an .xlsx upload")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        body = await file.read()
        tmp.write(body)
        tmp_path = Path(tmp.name)

    try:
        result = extract_canvas_v2(tmp_path)
    except Exception as e:
        log.exception("extract_canvas_v2_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=f"extraction failed: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    log.info("extract_canvas_v2_request_complete", filename=file.filename,
             pli_count=len(result.plis), warning_count=len(result.warnings))
    return ExtractResponse(**result.model_dump())
