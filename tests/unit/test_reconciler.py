"""Tests for app/services/reconciler."""
from app.models.extraction import PLI, ExtractionResult
from app.models.artifacts import ValidationFinding, ValidationFindings
from app.enums.validation_severity import ValidationSeverity
from app.services.reconciler import reconcile, aggregate_confidence


def test_reconcile_lenient_attaches_findings_as_warnings():
    workflow = ExtractionResult(plis=[PLI(io_number="1", confidence={"io_number": 0.9})])
    findings = ValidationFindings(findings=[
        ValidationFinding(check="coverage", severity=ValidationSeverity.WARN,
                         message="low"),
    ])
    out = reconcile(workflow_out=workflow, validation_out=findings)
    assert len(out.plis) == 1
    assert any(w.check == "coverage" and w.severity == "warning" for w in out.warnings)


def test_aggregate_confidence_formula():
    workflow = ExtractionResult(plis=[
        PLI(io_number="1", confidence={"io_number": 0.8, "style_code": 0.6}),
    ])
    findings = ValidationFindings(findings=[])
    c = aggregate_confidence(workflow, findings)
    # 0.7 * mean(0.8, 0.6) + 0.3 * (1 - 0) = 0.7 * 0.7 + 0.3 = 0.79
    assert abs(c - 0.79) < 0.01
