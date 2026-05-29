"""POST /extract_canvas — upload xlsx, run canvas pipeline chain, return ExtractionResult."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.logs import get_logger
from app.schemas.extract import ExtractResponse
from app.services.canvas_extract_service import extract_canvas


log = get_logger(__name__)
router = APIRouter()


@router.post("/extract_canvas", response_model=ExtractResponse, tags=["extract"])
async def extract_canvas_endpoint(file: UploadFile) -> ExtractResponse:
    """Extract structured PLI / Stage JSON via the canvas-architecture chain.

    Parallel to `POST /extract` (legacy planner path). This endpoint runs the
    full canvas-architecture pipeline chain: WorkbookPhase → per-bundle
    extractors → validators → judges → reconciler. Same response contract
    as the legacy route; different internals.
    """
    log.info("extract_canvas_request_received", filename=file.filename,
             content_type=file.content_type)
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="expected an .xlsx upload")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        body = await file.read()
        tmp.write(body)
        tmp_path = Path(tmp.name)

    try:
        result = extract_canvas(tmp_path)
    except Exception as e:
        log.exception("extract_canvas_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=f"extraction failed: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    log.info("extract_canvas_request_complete", filename=file.filename,
             pli_count=len(result.plis), warning_count=len(result.warnings))
    return ExtractResponse(**result.model_dump())
