"""StageWinsValidator — date identifier findings must not land in a StageArena.

A `StageArena` is the rectangular region of a detected stage band's
planned-date cells. A cell inside an arena belongs to that stage's
`planned_date` sub-field, not to a top-level date identifier
(`delivery_date`, `shipment_date`, `ex_fty_date`).

When a date-identifier extractor claims a cell that the structure
phase already attributed to a stage band, the stage band wins —
the extractor's claim is almost certainly a misroute (the date strip
inside the stage band was misidentified as a top-level date column).
The validator emits one `warning` per offending finding so downstream
judges can arbitrate.

Coverage uses an inclusive rect-containment check: a finding at
`(col, row)` is "inside" arena `Rect(r0, c0, r1, c1)` when
`r0 ≤ row ≤ r1` AND `c0 ≤ col ≤ c1`.
"""
from __future__ import annotations

from haystack import component
from openpyxl.utils import column_index_from_string

from app.artifacts.finding import Finding, ValidationWarning
from app.artifacts.structure import Rect
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.specs import DATE_IDENTIFIERS_AT_LEAST_ONE


_DATE_IDENTIFIERS: frozenset[str] = frozenset(DATE_IDENTIFIERS_AT_LEAST_ONE)


@component
class StageWinsValidator(Component):
    """Emit a warning per date-identifier finding whose cell sits inside a StageArena."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(warnings=list[ValidationWarning])
    def run(self, findings: list[Finding], bundle: ClusterAnchorBundle) -> dict:
        return {"warnings": _check_no_date_identifier_inside_stage_arena(findings, bundle)}


def _check_no_date_identifier_inside_stage_arena(
    findings: list[Finding],
    bundle: ClusterAnchorBundle,
) -> list[ValidationWarning]:
    """Flag each date-identifier finding whose value_coord lies in a StageArena.

    Iterates date-identifier findings only (`delivery_date`,
    `shipment_date`, `ex_fty_date`) and tests each against every arena
    rect. When any arena contains the finding's cell, emit one
    `stage_wins_over_date_identifier` warning naming the canonical,
    the cell, and the arena that captured it.
    """
    arenas = [arena.rect for arena in bundle.bag.stage_arenas]
    if not arenas:
        return []

    warnings: list[ValidationWarning] = []
    for finding in findings:
        if finding.canonical not in _DATE_IDENTIFIERS:
            continue
        col_letter, row = finding.value_coord
        col = column_index_from_string(col_letter)
        for arena in arenas:
            if _rect_contains(arena, row, col):
                warnings.append(ValidationWarning(
                    name="stage_wins_over_date_identifier",
                    severity="warning",
                    message=(
                        f"`{finding.canonical}` finding at "
                        f"({col_letter}{row}) sits inside StageArena "
                        f"rows {arena.r0}–{arena.r1} cols "
                        f"{arena.c0}–{arena.c1} — the cell belongs to "
                        f"a stage's planned_date, not a top-level date "
                        f"identifier."
                    ),
                    affects_findings=[finding],
                ))
                break
    return warnings


def _rect_contains(rect: Rect, row: int, col: int) -> bool:
    """Inclusive containment: (row, col) lies within `rect`."""
    return rect.r0 <= row <= rect.r1 and rect.c0 <= col <= rect.c1
