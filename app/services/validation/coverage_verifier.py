"""CoverageVerifier — flags when extracted PLI count drops below `floor`
× candidate-row count.

Catches silent under-extraction (e.g. MAIN FALL KIDS #1: extracted 2 PLIs
from a sheet whose boundary range had ~85 candidate rows)."""
from __future__ import annotations
from haystack import component
from app.models.extraction import ExtractionResult
from app.models.artifacts import (
    PLIBoundaries, ValidationFinding, ValidationFindings,
)
from app.enums.validation_severity import ValidationSeverity
from app.core.telemetry import validator_findings_total


@component
class CoverageVerifier:
    def __init__(self, boundaries: list[PLIBoundaries], floor: float = 0.8):
        self.boundaries = boundaries
        self.floor = floor

    @component.output_types(findings=ValidationFindings)
    def run(self, extraction: ExtractionResult) -> dict:
        findings: list[ValidationFinding] = []
        total_candidate_rows = 0
        for b in self.boundaries:
            if b.pattern == "one_sheet_per_pli":
                total_candidate_rows += len(b.sheet_iter)
                continue
            if b.data_start_row is None or b.data_end_row is None:
                continue
            total_candidate_rows += (b.data_end_row - b.data_start_row + 1)
        if total_candidate_rows == 0:
            return {"findings": ValidationFindings(findings=findings)}
        ratio = len(extraction.plis) / total_candidate_rows
        if ratio < self.floor:
            findings.append(ValidationFinding(
                check="coverage",
                severity=ValidationSeverity.WARN,
                message=(f"extracted {len(extraction.plis)} PLIs from "
                        f"{total_candidate_rows} candidate rows "
                        f"(ratio {ratio:.2f} < floor {self.floor})"),
            ))
            validator_findings_total.labels(check="coverage", severity="warn").inc()
        return {"findings": ValidationFindings(findings=findings)}
