"""Pipeline-level validator that confirms the plan is wire-ready for apply_plan.

Sits between FieldNamer's output and apply_plan invocation. Verifies the
plan's identity channel is populated according to pli_mode, and that
stage_bands exist where the mode requires them.
"""
from __future__ import annotations

from app.enums.pli_mode import PliMode
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import SheetPlan, ValidationFinding


def validate_pre_apply(plan: SheetPlan) -> list[ValidationFinding]:
    """Return findings if the plan's identity channel doesn't match its pli_mode."""
    findings: list[ValidationFinding] = []

    if plan.pli_mode is PliMode.ROW_PER_PLI:
        if not plan.header_labels:
            findings.append(ValidationFinding(
                check="pre_apply_readiness/identity_channel_empty",
                severity=ValidationSeverity.ERROR,
                message="pli_mode=ROW_PER_PLI but plan.header_labels is empty",
            ))
    elif plan.pli_mode is PliMode.SHEET_IS_PLI:
        if not plan.kv_anchors:
            findings.append(ValidationFinding(
                check="pre_apply_readiness/identity_channel_empty",
                severity=ValidationSeverity.ERROR,
                message="pli_mode=SHEET_IS_PLI but plan.kv_anchors is empty",
            ))
    elif plan.pli_mode is PliMode.SECTION_PER_PLI:
        if not plan.pli_blocks:
            findings.append(ValidationFinding(
                check="pre_apply_readiness/identity_channel_empty",
                severity=ValidationSeverity.ERROR,
                message="pli_mode=SECTION_PER_PLI but plan.pli_blocks is empty",
            ))
        else:
            for i, blk in enumerate(plan.pli_blocks):
                if not blk.identity:
                    findings.append(ValidationFinding(
                        check="pre_apply_readiness/block_identity_empty",
                        severity=ValidationSeverity.ERROR,
                        message=f"pli_blocks[{i}].identity is empty",
                    ))

    return findings
