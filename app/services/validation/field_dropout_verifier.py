"""FieldDropoutVerifier — flags any canonical field populated in < floor of PLIs."""
from __future__ import annotations
from haystack import component
from app.models.extraction import ExtractionResult
from app.models.artifacts import ValidationFinding, ValidationFindings
from app.enums.validation_severity import ValidationSeverity
from app.core.telemetry import validator_findings_total


_FIELDS_TO_TRACK = ("io_number", "style_code", "color_code",
                    "fabric_code", "delivery_date", "quantity")


@component
class FieldDropoutVerifier:
    def __init__(self, floor: float = 0.5):
        self.floor = floor

    @component.output_types(findings=ValidationFindings)
    def run(self, extraction: ExtractionResult) -> dict:
        findings: list[ValidationFinding] = []
        n = len(extraction.plis) or 1
        for field in _FIELDS_TO_TRACK:
            populated = sum(1 for p in extraction.plis
                            if getattr(p, field, None) not in (None, ""))
            ratio = populated / n
            if ratio < self.floor:
                findings.append(ValidationFinding(
                    check="field_dropout",
                    severity=ValidationSeverity.WARN,
                    message=(f"{field!r} populated in {populated}/{n} PLIs "
                            f"(ratio {ratio:.2f} < floor {self.floor})"),
                    field=field,
                ))
                validator_findings_total.labels(check="field_dropout",
                                               severity="warn").inc()
        return {"findings": ValidationFindings(findings=findings)}
