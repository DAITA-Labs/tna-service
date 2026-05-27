"""Finding, Verdict, and ValidationWarning artifact contracts."""
from __future__ import annotations

from app.artifacts.finding import Confidence, Finding, ValidationWarning, Verdict


def test_finding_construction() -> None:
    """A Finding carries canonical + coords + value + confidence + evidence."""
    finding = Finding(
        canonical="io_number",
        label_coord=("K", 2),
        value_coord=("K", 4),
        value="131673",
        confidence=Confidence.HIGH,
        evidence=["HEADER_BAND_MEMBER", "SAME_LENGTH_STRIP"],
    )

    assert finding.canonical == "io_number"
    assert finding.value == "131673"
    assert finding.confidence is Confidence.HIGH
    assert "SAME_LENGTH_STRIP" in finding.evidence
    assert finding.decision_notes is None


def test_finding_decision_notes_optional() -> None:
    """decision_notes captures the why for downstream traceability."""
    finding = Finding(
        canonical="quantity",
        label_coord=("M", 3),
        value_coord=("M", 4),
        value=500,
        confidence=Confidence.MEDIUM,
        decision_notes="claimed by intstrip_large + word_boundary_qty match",
    )
    assert finding.decision_notes is not None
    assert "intstrip_large" in finding.decision_notes


def test_verdict_decisions() -> None:
    """Verdict supports the three legal decisions."""
    keep = Verdict(decision="keep", reason="high-confidence det")
    drop = Verdict(decision="drop", reason="anti-pattern matched")
    rewrite = Verdict(
        decision="rewrite",
        reason="alternative column wins by spec priority",
        alternative_coord=("J", 4),
    )

    assert keep.decision == "keep"
    assert drop.decision == "drop"
    assert rewrite.alternative_coord == ("J", 4)


def test_verdict_default_confidence_medium() -> None:
    """Verdict.confidence defaults to MEDIUM when not provided."""
    v = Verdict(decision="keep", reason="ok")
    assert v.confidence is Confidence.MEDIUM


def test_validation_warning_severity_levels() -> None:
    """ValidationWarning accepts info / warning / error."""
    info = ValidationWarning(name="repeating_header_pattern", severity="info", message="...")
    warn = ValidationWarning(name="orphan_dates", severity="warning", message="...")
    err = ValidationWarning(name="no_header_detected", severity="error", message="...")

    assert info.severity == "info"
    assert warn.severity == "warning"
    assert err.severity == "error"


def test_validation_warning_affects() -> None:
    """affects() identifies which findings the warning concerns."""
    f1 = Finding(
        canonical="io_number",
        label_coord=("K", 2),
        value_coord=("K", 4),
        value="X",
        confidence=Confidence.HIGH,
    )
    f2 = Finding(
        canonical="quantity",
        label_coord=("M", 2),
        value_coord=("M", 4),
        value=500,
        confidence=Confidence.HIGH,
    )

    warning = ValidationWarning(
        name="cardinality_mismatch",
        severity="error",
        message="io_number count != PLI count",
        affects_findings=[f1],
    )

    assert warning.affects(f1) is True
    assert warning.affects(f2) is False


def test_confidence_enum_is_strenum() -> None:
    """Confidence values serialise as their str names — useful for JSON/log."""
    assert Confidence.HIGH.value == "high"
    assert Confidence.MEDIUM.value == "medium"
    assert Confidence.LOW.value == "low"
