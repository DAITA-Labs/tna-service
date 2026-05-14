"""Response shape for /extract endpoint."""
from __future__ import annotations

from app.models.extraction import ExtractionResult


class ExtractResponse(ExtractionResult):
    """Extraction result with metadata: source document and validation warnings."""
