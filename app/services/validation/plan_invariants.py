"""Tier 1 plan validators — structural invariants of a SheetPlan as a graph.

Errors here mean the plan is corrupt; the orchestrator should re-plan with
hints, not call PlanReviewer.
"""
from __future__ import annotations

from app.core.logs import get_logger
from app.enums.row_role import RowRole
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import SheetPlan, ValidationFinding

log = get_logger(__name__)


def _error(check: str, msg: str) -> ValidationFinding:
    """Build an ERROR finding for the given check."""
    return ValidationFinding(check=check, severity=ValidationSeverity.ERROR, message=msg)


def _warn(check: str, msg: str) -> ValidationFinding:
    """Build a WARN finding for the given check."""
    return ValidationFinding(check=check, severity=ValidationSeverity.WARN, message=msg)


def _check_reference_integrity(plan: SheetPlan) -> list[ValidationFinding]:
    """Anchor rows must not carry anchor_idx; child rows must point at a real anchor."""
    out: list[ValidationFinding] = []
    anchors = {r.idx for r in plan.rows if r.role is RowRole.ANCHOR}
    for r in plan.rows:
        if r.role is RowRole.ANCHOR and r.anchor_idx is not None:
            out.append(_error("reference_integrity",
                               f"ANCHOR row {r.idx} has non-null anchor_idx={r.anchor_idx}"))
        if r.role is RowRole.CHILD:
            if r.anchor_idx is None:
                out.append(_error("reference_integrity",
                                   f"CHILD row {r.idx} has no anchor_idx"))
            elif r.anchor_idx not in anchors:
                out.append(_error("reference_integrity",
                                   f"CHILD row {r.idx} anchor_idx={r.anchor_idx} not in ANCHOR rows"))
    return out


def _check_row_uniqueness(plan: SheetPlan) -> list[ValidationFinding]:
    """Each row.idx may appear at most once across plan.rows."""
    out: list[ValidationFinding] = []
    seen: set[int] = set()
    for r in plan.rows:
        if r.idx in seen:
            out.append(_error("row_uniqueness", f"row idx {r.idx} appears more than once"))
        seen.add(r.idx)
    return out


def _check_header_contiguity(plan: SheetPlan) -> list[ValidationFinding]:
    """Header rows must form a contiguous range; no data row may precede them."""
    out: list[ValidationFinding] = []
    if plan.header_rows:
        sorted_h = sorted(plan.header_rows)
        if sorted_h != list(range(sorted_h[0], sorted_h[-1] + 1)):
            out.append(_warn("header_contiguity", "header rows are not contiguous"))
        if plan.rows:
            max_h = max(plan.header_rows)
            for r in plan.rows:
                if r.role in (RowRole.ANCHOR, RowRole.CHILD) and r.idx < max_h:
                    out.append(_warn("header_contiguity",
                                      f"data row {r.idx} precedes max header row {max_h}"))
                    break
    return out


def _check_pli_block_non_overlap(plan: SheetPlan) -> list[ValidationFinding]:
    """Sorted by bbox start, no two pli_blocks may overlap."""
    out: list[ValidationFinding] = []
    blocks = sorted(plan.pli_blocks, key=lambda b: b.bbox[0])
    for i in range(len(blocks) - 1):
        if blocks[i].bbox[1] >= blocks[i + 1].bbox[0]:
            out.append(_error("pli_block_non_overlap",
                               f"blocks {blocks[i].id} {blocks[i].bbox} and "
                               f"{blocks[i+1].id} {blocks[i+1].bbox} overlap"))
    return out


def _check_sub_row_consistency(plan: SheetPlan) -> list[ValidationFinding]:
    """Within a group, all members must agree on whether sub_row_role is set."""
    out: list[ValidationFinding] = []
    by_group: dict[int, list] = {}
    for r in plan.rows:
        if r.group_id is not None:
            by_group.setdefault(r.group_id, []).append(r)
    for gid, members in by_group.items():
        sub_set = {bool(m.sub_row_role) for m in members}
        if len(sub_set) > 1:
            out.append(_warn("sub_row_consistency",
                              f"group {gid} mixes sub_row_role set + unset"))
    return out


def validate_invariants(plan: SheetPlan) -> list[ValidationFinding]:
    """Run all Tier 1 structural invariant checks against a SheetPlan.

    Returns the concatenated findings. ERROR severity means the plan is corrupt
    and the orchestrator should re-plan with hints rather than call PlanReviewer.
    """
    findings = [
        *_check_reference_integrity(plan),
        *_check_row_uniqueness(plan),
        *_check_header_contiguity(plan),
        *_check_pli_block_non_overlap(plan),
        *_check_sub_row_consistency(plan),
    ]
    if findings:
        log.info(
            "plan_invariants_findings",
            sheet=plan.sheet,
            error_count=sum(1 for f in findings if f.severity == ValidationSeverity.ERROR),
            warn_count=sum(1 for f in findings if f.severity == ValidationSeverity.WARN),
        )
    return findings
