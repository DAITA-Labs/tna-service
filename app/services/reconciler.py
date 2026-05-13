"""Reconciler — merges workflow + validation outputs.

V1 lenient: workflow passes through unchanged; validation findings attach as
Warnings; extraction_confidence is recomputed from the spec's V1 formula:
  0.7 * mean(workflow_per_field_confidence) + 0.3 * (1 - validator_warn_rate)
"""
from __future__ import annotations
from app.models.extraction import ExtractionResult, Warning
from app.models.artifacts import ValidationFindings, ValidationFinding
from app.enums.validation_severity import ValidationSeverity
from app.core.logs import get_logger

log = get_logger(__name__)


def _finding_to_warning(f: ValidationFinding) -> Warning:
    """Map validator severity to Warning severity ('warn' -> 'warning')."""
    sev_map = {
        ValidationSeverity.INFO: "info",
        ValidationSeverity.WARN: "warning",
        ValidationSeverity.ERROR: "error",
    }
    return Warning(
        message=f.message,
        severity=sev_map.get(f.severity, "warning"),
        pli_index=f.pli_index,
        field=f.field,
        check=f.check,
    )


def aggregate_confidence(workflow: ExtractionResult,
                        validation: ValidationFindings) -> float:
    """V1 formula: 0.7 * mean(workflow_conf) + 0.3 * (1 - warn_rate)."""
    field_confs = []
    for pli in workflow.plis:
        if pli.confidence:
            field_confs.extend(pli.confidence.values())
    workflow_mean = sum(field_confs) / len(field_confs) if field_confs else 0.0
    return round(0.7 * workflow_mean + 0.3 * (1.0 - validation.warn_rate), 4)


def reconcile(workflow_out: ExtractionResult,
              validation_out: ValidationFindings) -> ExtractionResult:
    """V1 lenient: workflow passes through, findings → warnings."""
    result = workflow_out.model_copy(deep=True)
    for f in validation_out.findings:
        result.warnings.append(_finding_to_warning(f))
    result.extraction_confidence = aggregate_confidence(workflow_out, validation_out)
    log.info("reconcile_complete", pli_count=len(result.plis),
             warning_count=len(result.warnings),
             confidence=result.extraction_confidence)
    return result
