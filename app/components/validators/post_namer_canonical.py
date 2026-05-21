"""Pipeline-level validator that asserts FieldNamer didn't silently drop labels.

Sits between FieldNamer's output and apply_plan. For every label detected
by the planner (in header_labels, kv_anchors, pli_blocks[].identity, and
stage_bands[].stage_columns), the name_map must contain either a non-empty
canonical name OR the literal string "ignore". A silent omission means a
label is dropped from extraction without explanation.
"""
from __future__ import annotations

from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import CanonicalNameMap, SheetPlan, ValidationFinding


def validate_post_namer(
    plan: SheetPlan, name_map: CanonicalNameMap,
) -> list[ValidationFinding]:
    """Return findings for every detected label missing from name_map."""
    findings: list[ValidationFinding] = []

    detected_field_labels = _collect_field_labels(plan)
    for label in detected_field_labels:
        if label not in name_map.field_labels:
            findings.append(ValidationFinding(
                check="post_namer_canonical/field_label_dropped",
                severity=ValidationSeverity.WARN,
                message=f"label {label!r} was detected but not present in CanonicalNameMap.field_labels",
            ))

    detected_stage_names = _collect_stage_names(plan)
    for name in detected_stage_names:
        if name not in name_map.stage_names:
            findings.append(ValidationFinding(
                check="post_namer_canonical/stage_name_dropped",
                severity=ValidationSeverity.WARN,
                message=f"stage name {name!r} was detected but not present in CanonicalNameMap.stage_names",
            ))

    return findings


def _collect_field_labels(plan: SheetPlan) -> set[str]:
    """Aggregate raw labels from all three identity channels."""
    labels: set[str] = {hl.raw for hl in plan.header_labels}
    labels.update(kv.field for kv in plan.kv_anchors)
    for blk in plan.pli_blocks:
        labels.update(kv.field for kv in blk.identity)
    return labels


def _collect_stage_names(plan: SheetPlan) -> set[str]:
    """Aggregate stage column names from sheet-level + block-level bands."""
    names: set[str] = set()
    for band in plan.stage_bands:
        for sc in band.stage_columns:
            names.add(sc.name)
    for blk in plan.pli_blocks:
        for band in blk.stage_bands:
            for sc in band.stage_columns:
                names.add(sc.name)
    return names
