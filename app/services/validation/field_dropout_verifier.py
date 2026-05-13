"""FieldDropoutVerifier — flags any canonical field populated in < floor of PLIs."""
from __future__ import annotations
from haystack import component
from app.models.extraction import ExtractionResult
from app.models.artifacts import ValidationFinding, ValidationFindings
from app.enums.validation_severity import ValidationSeverity
from app.core.telemetry import validator_findings_total
from app.core.logs import get_logger

log = get_logger(__name__)


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
        for f in _FIELDS_TO_TRACK:
            p = sum(1 for pli in extraction.plis
                    if getattr(pli, f, None) not in (None, ""))
            t = n
            ratio = p / t
            if ratio < self.floor:
                log.warning("field_dropout_warn", field=f, populated=p,
                            total=t, ratio=round(ratio, 4))
                findings.append(ValidationFinding(
                    check="field_dropout",
                    severity=ValidationSeverity.WARN,
                    message=(f"{f!r} populated in {p}/{t} PLIs "
                            f"(ratio {ratio:.2f} < floor {self.floor})"),
                    field=f,
                ))
                validator_findings_total.labels(check="field_dropout",
                                               severity="warn").inc()
        return {"findings": ValidationFindings(findings=findings)}
