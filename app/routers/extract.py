"""POST /extract — upload xlsx, run orchestrator, return ExtractionResult."""
from __future__ import annotations
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, HTTPException
from app.schemas.extract import ExtractResponse
from app.services.extraction import extract
from app.core.logs import get_logger

log = get_logger(__name__)
router = APIRouter()


@router.post("/extract", response_model=ExtractResponse, tags=["extract"])
async def extract_endpoint(file: UploadFile) -> ExtractResponse:
    """Extract structured PLI / Stage JSON from an uploaded TNA xlsx."""
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="expected an .xlsx upload")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        body = await file.read()
        tmp.write(body)
        tmp_path = Path(tmp.name)

    try:
        result = extract(tmp_path)
    except Exception as e:
        log.exception("extract_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=f"extraction failed: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    return ExtractResponse(**result.model_dump())
