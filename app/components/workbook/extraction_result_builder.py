"""ExtractionResultBuilder — pipeline component that assembles ExtractionResult."""
from __future__ import annotations

from haystack import component

from app.components._base import Component
from app.models.extraction import ExtractionResult, PLI, Warning


@component
class ExtractionResultBuilder(Component):
    """Pipeline component: assembles a list of PLIs + warnings into an ExtractionResult."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(result=ExtractionResult)
    def run(
        self,
        plis: list,
        warnings: list,
        format_detected: str,
        source_file: str,
    ) -> dict:
        """Build and return an ExtractionResult from the per-sheet aggregate outputs."""
        return {"result": ExtractionResult(
            plis=plis,
            warnings=warnings,
            format_detected=format_detected,
            source_file=source_file,
        )}
