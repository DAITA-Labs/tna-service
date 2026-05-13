"""Tier 1 plan validators — structural invariants of a SheetPlan as a graph.

Errors here mean the plan is corrupt; the orchestrator should re-plan with
hints, not call PlanReviewer.
"""
from __future__ import annotations
from app.models.artifacts import SheetPlan, ValidationFinding
from app.enums.row_role import RowRole
from app.enums.validation_severity import ValidationSeverity


def _e(check: str, msg: str) -> ValidationFinding:
    return ValidationFinding(check=check, severity=ValidationSeverity.ERROR, message=msg)


def _w(check: str, msg: str) -> ValidationFinding:
    return ValidationFinding(check=check, severity=ValidationSeverity.WARN, message=msg)


def validate_invariants(plan: SheetPlan) -> list[ValidationFinding]:
    out: list[ValidationFinding] = []

    anchors = {r.idx for r in plan.rows if r.role is RowRole.ANCHOR}
    for r in plan.rows:
        if r.role is RowRole.ANCHOR and r.anchor_idx is not None:
            out.append(_e("reference_integrity",
                          f"ANCHOR row {r.idx} has non-null anchor_idx={r.anchor_idx}"))
        if r.role is RowRole.CHILD:
            if r.anchor_idx is None:
                out.append(_e("reference_integrity",
                              f"CHILD row {r.idx} has no anchor_idx"))
            elif r.anchor_idx not in anchors:
                out.append(_e("reference_integrity",
                              f"CHILD row {r.idx} anchor_idx={r.anchor_idx} not in ANCHOR rows"))

    seen: set[int] = set()
    for r in plan.rows:
        if r.idx in seen:
            out.append(_e("row_uniqueness", f"row idx {r.idx} appears more than once"))
        seen.add(r.idx)

    if plan.header_rows:
        sorted_h = sorted(plan.header_rows)
        if sorted_h != list(range(sorted_h[0], sorted_h[-1] + 1)):
            out.append(_w("header_contiguity", "header rows are not contiguous"))
        if plan.rows:
            max_h = max(plan.header_rows)
            for r in plan.rows:
                if r.role in (RowRole.ANCHOR, RowRole.CHILD) and r.idx < max_h:
                    out.append(_w("header_contiguity",
                                  f"data row {r.idx} precedes max header row {max_h}"))
                    break

    blocks = sorted(plan.pli_blocks, key=lambda b: b.bbox[0])
    for i in range(len(blocks) - 1):
        if blocks[i].bbox[1] >= blocks[i + 1].bbox[0]:
            out.append(_e("pli_block_non_overlap",
                          f"blocks {blocks[i].id} {blocks[i].bbox} and "
                          f"{blocks[i+1].id} {blocks[i+1].bbox} overlap"))

    by_group: dict[int, list] = {}
    for r in plan.rows:
        if r.group_id is not None:
            by_group.setdefault(r.group_id, []).append(r)
    for gid, members in by_group.items():
        sub_set = {bool(m.sub_row_role) for m in members}
        if len(sub_set) > 1:
            out.append(_w("sub_row_consistency",
                          f"group {gid} mixes sub_row_role set + unset"))

    return out
