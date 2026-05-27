"""SectionBoundaryResolver — RepeatingRowGroup → SectionBoundary records."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import (
    RepeatingRowGroup,
    SectionBoundary,
    StructureBag,
)
from app.components.structure.resolvers.section_boundary import resolve_section_boundaries


def _empty_canvas(n_rows: int = 100, n_cols: int = 30):
    return GridCanvas(
        n_rows=n_rows, n_cols=n_cols,
        cell_values=[[None] * n_cols for _ in range(n_rows)],
    )


def test_no_groups_means_no_boundaries() -> None:
    """An empty repeating_groups list produces no SectionBoundaries."""
    canvas = _empty_canvas()
    bag = StructureBag()
    boundaries = resolve_section_boundaries(canvas, bag)
    assert boundaries == []


def test_largest_group_drives_section_starts() -> None:
    """The largest RepeatingRowGroup is used; each row becomes a section start."""
    canvas = _empty_canvas(n_rows=100)
    bag = StructureBag()
    bag.repeating_groups = [
        RepeatingRowGroup(row_indices=(1, 20, 40, 60), signature="big"),
        RepeatingRowGroup(row_indices=(2, 80), signature="small"),
    ]
    boundaries = resolve_section_boundaries(canvas, bag)
    assert len(boundaries) == 4
    assert [b.start_row for b in boundaries] == [1, 20, 40, 60]


def test_section_end_row_is_next_start_minus_one() -> None:
    """Each section's end_row is the next start minus 1; last section ends at n_rows."""
    canvas = _empty_canvas(n_rows=100)
    bag = StructureBag()
    bag.repeating_groups = [
        RepeatingRowGroup(row_indices=(1, 20, 40), signature="x"),
    ]
    boundaries = resolve_section_boundaries(canvas, bag)
    assert boundaries[0].end_row == 19
    assert boundaries[1].end_row == 39
    assert boundaries[2].end_row == 100   # last section to sheet end


def test_section_ids_are_sequential() -> None:
    """Section IDs are 's0', 's1', 's2', ... in start-row order."""
    canvas = _empty_canvas()
    bag = StructureBag()
    bag.repeating_groups = [
        RepeatingRowGroup(row_indices=(50, 5, 30), signature="x"),  # unsorted on purpose
    ]
    boundaries = resolve_section_boundaries(canvas, bag)
    assert [b.section_id for b in boundaries] == ["s0", "s1", "s2"]
    assert [b.start_row for b in boundaries] == [5, 30, 50]


def test_single_member_group_ignored() -> None:
    """A group with only 1 member doesn't qualify — no boundaries emitted."""
    canvas = _empty_canvas()
    bag = StructureBag()
    bag.repeating_groups = [
        RepeatingRowGroup(row_indices=(7,), signature="single"),
    ]
    boundaries = resolve_section_boundaries(canvas, bag)
    assert boundaries == []
