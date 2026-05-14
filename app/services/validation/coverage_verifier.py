"""CoverageVerifier — flags when extracted PLI count drops below `floor`
× candidate-row count.

Catches silent under-extraction (e.g. MAIN FALL KIDS #1: extracted 2 PLIs
from a sheet whose boundary range had ~85 candidate rows)."""
from __future__ import annotations

from haystack import component

from app.core.logs import get_logger
from app.core.telemetry import validator_findings_total
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import PLIBoundaries, ValidationFinding, ValidationFindings
from app.models.extraction import ExtractionResult

log = get_logger(__name__)


@component
class CoverageVerifier:
    """Validates PLI count against candidate-row count; emits a finding when the ratio falls below `floor`."""

    def __init__(self, boundaries: list[PLIBoundaries], floor: float = 0.8):
        self.boundaries = boundaries
        self.floor = floor

    @component.output_types(findings=ValidationFindings)
    def run(self, extraction: ExtractionResult) -> dict:
        """Run coverage check and return findings keyed by 'findings'."""
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
        pli_count = len(extraction.plis)
        ratio = pli_count / total_candidate_rows
        if ratio < self.floor:
            log.warning("coverage_warn", pli_count=pli_count,
                        candidate_rows=total_candidate_rows, ratio=round(ratio, 4))
            findings.append(ValidationFinding(
                check="coverage",
                severity=ValidationSeverity.WARN,
                message=(f"extracted {pli_count} PLIs from "
                        f"{total_candidate_rows} candidate rows "
                        f"(ratio {ratio:.2f} < floor {self.floor})"),
            ))
            validator_findings_total.add(1, {"check": "coverage", "severity": "warn"})
        return {"findings": ValidationFindings(findings=findings)}
