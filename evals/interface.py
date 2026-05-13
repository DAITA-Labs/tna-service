"""ExtractorProtocol — the eval framework's view of any extractor.

Eval imports only this Protocol + app.models. Any class with an
`extract(workbook_path: Path) -> ExtractionResult` method works.
This is the only contract between the eval framework and any extractor
implementation (today's microservice, future rewrites, mock extractors).
"""
from __future__ import annotations
from pathlib import Path
from typing import Protocol, runtime_checkable
from app.models.extraction import ExtractionResult


@runtime_checkable
class ExtractorProtocol(Protocol):
    def extract(self, workbook_path: Path) -> ExtractionResult: ...
