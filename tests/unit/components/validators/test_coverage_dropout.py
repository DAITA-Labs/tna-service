"""Tests for coverage_verifier + field_dropout_verifier."""
from app.models.extraction import PLI, ExtractionResult
from app.models.artifacts import PLIBoundaries
from app.components.validators.coverage_verifier import CoverageVerifier
from app.components.validators.field_dropout_verifier import FieldDropoutVerifier


def test_coverage_warns_when_extracted_lt_80pct():
    boundaries = PLIBoundaries(sheet="S", pattern="one_row_per_pli",
                              data_start_row=4, data_end_row=100, confidence=1.0)
    # Range = 97 rows; extracted only 5.
    result = ExtractionResult(plis=[PLI(io_number=str(i)) for i in range(5)])
    v = CoverageVerifier(boundaries=[boundaries], floor=0.8)
    findings = v.run(extraction=result)["findings"].findings
    assert any(f.check == "coverage" and f.severity == "warn" for f in findings)


def test_coverage_passes_when_extracted_ge_80pct():
    boundaries = PLIBoundaries(sheet="S", pattern="one_row_per_pli",
                              data_start_row=4, data_end_row=10, confidence=1.0)
    # Range = 7 rows; extracted 6 (85%).
    result = ExtractionResult(plis=[PLI(io_number=str(i)) for i in range(6)])
    v = CoverageVerifier(boundaries=[boundaries], floor=0.8)
    assert not v.run(extraction=result)["findings"].findings


def test_field_dropout_warns_when_field_under_50pct():
    plis = [
        PLI(io_number="1", style_code="A"),
        PLI(io_number="2"),
        PLI(io_number="3"),
        PLI(io_number="4"),
    ]
    result = ExtractionResult(plis=plis)
    v = FieldDropoutVerifier(floor=0.5)
    findings = v.run(extraction=result)["findings"].findings
    # style_code populated in only 1/4 (25% < 50% floor)
    assert any(f.check == "field_dropout" and f.field == "style_code" for f in findings)
