"""Tier 1 invariants: exactly_one_identity_channel + mode_channel_consistency."""
from app.enums.pli_mode import PliMode
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import (
    HeaderLabel,
    KVAnchor,
    PliBlock,
    SheetPlan,
)
from app.services.validation.plan_invariants import validate_invariants


def test_row_per_pli_with_header_labels_passes_invariants() -> None:
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_labels=[HeaderLabel(raw="IO", col="B", row=3)],
    )
    findings = validate_invariants(plan)
    error_checks = {f.check for f in findings if f.severity == ValidationSeverity.ERROR}
    assert "exactly_one_identity_channel" not in error_checks
    assert "mode_channel_consistency" not in error_checks


def test_two_channels_populated_fires_error() -> None:
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_labels=[HeaderLabel(raw="IO", col="B", row=3)],
        kv_anchors=[KVAnchor(label_cell="A1", value_cell="B1", field="io")],
    )
    findings = validate_invariants(plan)
    assert any(
        f.check == "exactly_one_identity_channel" and f.severity == ValidationSeverity.ERROR
        for f in findings
    )


def test_mode_channel_mismatch_fires_error() -> None:
    """SHEET_IS_PLI but header_labels populated instead of kv_anchors."""
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.SHEET_IS_PLI,
        header_labels=[HeaderLabel(raw="IO", col="B", row=3)],
    )
    findings = validate_invariants(plan)
    assert any(
        f.check == "mode_channel_consistency" and f.severity == ValidationSeverity.ERROR
        for f in findings
    )


def test_no_channel_populated_is_not_an_error() -> None:
    """An empty plan is allowed during planner bring-up (caught by other validators)."""
    plan = SheetPlan(sheet="S", pli_mode=PliMode.ROW_PER_PLI)
    findings = validate_invariants(plan)
    error_checks = {f.check for f in findings if f.severity == ValidationSeverity.ERROR}
    assert "exactly_one_identity_channel" not in error_checks
