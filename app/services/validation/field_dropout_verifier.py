"""FieldDropoutVerifier — flags any canonical field populated in fewer than `floor` of PLIs."""
from __future__ import annotations

from haystack import component

from app.core.logs import get_logger
from app.core.telemetry import validator_findings_total
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import ValidationFinding, ValidationFindings
from app.models.extraction import ExtractionResult

log = get_logger(__name__)


_FIELDS_TO_TRACK = ("io_number", "style_code", "color_code",
                    "fabric_code", "delivery_date", "quantity")


@component
class FieldDropoutVerifier:
    """Validates per-field population rates across all PLIs; emits a finding when any field falls below `floor`."""

    def __init__(self, floor: float = 0.5):
        self.floor = floor

    @component.output_types(findings=ValidationFindings)
    def run(self, extraction: ExtractionResult) -> dict:
        """Check each tracked field's population ratio and return findings keyed by 'findings'."""
        findings: list[ValidationFinding] = []
        total = len(extraction.plis) or 1
        for field in _FIELDS_TO_TRACK:
            populated = sum(
                1 for pli in extraction.plis
                if getattr(pli, field, None) not in (None, "")
            )
            ratio = populated / total
            if ratio < self.floor:
                log.warning("field_dropout_warn", field=field, populated=populated,
                            total=total, ratio=round(ratio, 4))
                findings.append(ValidationFinding(
                    check="field_dropout",
                    severity=ValidationSeverity.WARN,
                    message=(f"{field!r} populated in {populated}/{total} PLIs "
                            f"(ratio {ratio:.2f} < floor {self.floor})"),
                    field=field,
                ))
                validator_findings_total.add(
                    1, {"check": "field_dropout", "severity": "warn"}
                )
        return {"findings": ValidationFindings(findings=findings)}
