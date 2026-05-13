"""Request / response shapes for /extract."""
from __future__ import annotations
from app.models.extraction import ExtractionResult


class ExtractResponse(ExtractionResult):
    """Same shape as ExtractionResult — surfaces source_cells, warnings, etc."""
