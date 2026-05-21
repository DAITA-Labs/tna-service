"""Reconciler — merges workflow + validation outputs.

V1 lenient: workflow passes through unchanged; validation findings attach as
Warnings; extraction_confidence is recomputed from the spec's V1 formula:
  0.7 * mean(workflow_per_field_confidence) + 0.3 * (1 - validator_warn_rate)

`Reconciler` is the Haystack `@component` wrapper around `reconcile`.
"""
from __future__ import annotations

from haystack import component

from app.components._base import Component
from app.core.logs import get_logger
from app.models.artifacts import ValidationFinding, ValidationFindings
from app.models.extraction import ExtractionResult, Warning

log = get_logger(__name__)


def _finding_to_warning(f: ValidationFinding) -> Warning:
    """Convert a ValidationFinding to a Warning using the enum value directly."""
    return Warning(
        message=f.message,
        severity=f.severity.value,
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


@component
class Reconciler(Component):
    """Pipeline component that merges workflow output + validation findings."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(result=ExtractionResult)
    def run(
        self,
        workflow_out: ExtractionResult,
        source_findings: ValidationFindings,
        header_findings: ValidationFindings,
        coverage_findings: ValidationFindings,
        dropout_findings: ValidationFindings,
    ) -> dict:
        """Merge all verifier findings with the workflow result."""
        all_findings = ValidationFindings(findings=(
            source_findings.findings
            + header_findings.findings
            + coverage_findings.findings
            + dropout_findings.findings
        ))
        return {"result": reconcile(workflow_out=workflow_out, validation_out=all_findings)}
