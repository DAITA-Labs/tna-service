"""MergeAlignmentValidator — sibling identifiers respect io_number's merge partition.

When a TNA sheet groups child rows under a parent PLI by vertically
merging the `io_number` cell across the child rows, every sibling
identifier column should respect the same row-group partition. The
sibling column is allowed to:

  - merge identically across the same row range, or
  - carry a single value on the anchor row with blanks below.

What it must NOT do is carry distinct findings on different rows
within the merge range — that contradicts the io_number partition
("one PLI rows 4-6" vs "three style codes on rows 4, 5, 6").

The validator emits one `warning` per (io_number merge, sibling
canonical) where the sibling has more than one finding inside the
merge's row range.
"""
from __future__ import annotations

from collections import defaultdict

from haystack import component
from openpyxl.utils import column_index_from_string

from app.artifacts.finding import Finding, ValidationWarning
from app.artifacts.structure import Rect
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component


@component
class MergeAlignmentValidator(Component):
    """Emit warnings where sibling identifier columns split an io_number merge group."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(warnings=list[ValidationWarning])
    def run(self, findings: list[Finding], bundle: ClusterAnchorBundle) -> dict:
        return {"warnings": _check_siblings_respect_io_number_merges(findings, bundle)}


def _check_siblings_respect_io_number_merges(
    findings: list[Finding],
    bundle: ClusterAnchorBundle,
) -> list[ValidationWarning]:
    """Flag sibling identifiers with multiple findings inside an io_number merge.

    Determines the io_number column(s) from `findings`, locates vertical
    merges at those columns in `bundle.bag.merge_spans`, and counts each
    other canonical's findings within each merge's row range. Multiple
    findings inside the merge → row-group violation warning.
    """
    io_cols = _io_number_columns(findings)
    if not io_cols:
        return []

    io_merges = _vertical_merges_at_columns(bundle, io_cols)
    if not io_merges:
        return []

    by_canonical = _findings_by_canonical_excluding(findings, "io_number")

    warnings: list[ValidationWarning] = []
    for merge in io_merges:
        for canonical in sorted(by_canonical):
            siblings = [
                f for f in by_canonical[canonical]
                if merge.r0 <= f.value_coord[1] <= merge.r1
            ]
            if len(siblings) <= 1:
                continue
            rows = sorted(f.value_coord[1] for f in siblings)
            warnings.append(ValidationWarning(
                name="merge_alignment_violation",
                severity="warning",
                message=(
                    f"`io_number` merges rows {merge.r0}-{merge.r1} into "
                    f"one PLI, but `{canonical}` has {len(siblings)} "
                    f"distinct findings across rows {rows} within that "
                    f"range — sibling identifier columns should respect "
                    f"the io_number row-group partition."
                ),
                affects_findings=siblings,
            ))
    return warnings


def _io_number_columns(findings: list[Finding]) -> set[int]:
    """Return the 1-indexed columns where any io_number finding lives."""
    return {
        column_index_from_string(f.value_coord[0])
        for f in findings if f.canonical == "io_number"
    }


def _vertical_merges_at_columns(bundle: ClusterAnchorBundle, cols: set[int]) -> list[Rect]:
    """Return vertical MergeSpan rects whose column lies in `cols`."""
    return [
        m.rect for m in bundle.bag.merge_spans
        if m.orientation == "vertical"
        and m.rect.c0 == m.rect.c1
        and m.rect.c0 in cols
    ]


def _findings_by_canonical_excluding(
    findings: list[Finding],
    excluded: str,
) -> dict[str, list[Finding]]:
    """Group `findings` by canonical, skipping the named one."""
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        if f.canonical == excluded:
            continue
        grouped[f.canonical].append(f)
    return grouped
