"""SectionBoundaryResolver — convert RepeatingRowGroups into PLI section starts.

In SECTION_PER_PLI layouts (GUESS, MAIN FALL), the same header row
repeats above every PLI block. Each occurrence marks the start of a
new section. SectionBoundaryResolver:

- Picks the largest RepeatingRowGroup (most member rows) as the
  section-start signature.
- For each start-row in the group, emits a SectionBoundary covering
  rows from the start through one row before the next start (or the
  end of the sheet for the last section).

A workbook without strong repeating-row patterns emits no boundaries —
the sheet is treated as a single section by downstream consumers.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import RepeatingRowGroup, SectionBoundary, StructureBag


_MIN_GROUP_SIZE = 2


def resolve_section_boundaries(canvas: GridCanvas, bag: StructureBag) -> list[SectionBoundary]:
    """Emit one SectionBoundary per occurrence of the dominant repeating header.

    Returns and stores into `bag.section_boundaries`.
    """
    primary_group = _select_primary_group(bag.repeating_groups)
    if primary_group is None:
        bag.section_boundaries = []
        return []

    starts = sorted(primary_group.row_indices)
    boundaries: list[SectionBoundary] = []
    for i, start in enumerate(starts):
        end = (starts[i + 1] - 1) if i + 1 < len(starts) else canvas.n_rows
        boundaries.append(SectionBoundary(
            start_row=start,
            end_row=end,
            section_id=f"s{i}",
        ))
    bag.section_boundaries = boundaries
    return boundaries


def _select_primary_group(groups: list[RepeatingRowGroup]) -> RepeatingRowGroup | None:
    """Pick the largest group with ≥ MIN_GROUP_SIZE members; None if none qualify."""
    eligible = [g for g in groups if len(g.row_indices) >= _MIN_GROUP_SIZE]
    if not eligible:
        return None
    return max(eligible, key=lambda g: len(g.row_indices))
