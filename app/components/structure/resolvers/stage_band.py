"""StageBandResolver — pair each StageArena with its name cell from MergeSpans.

A StageBand is a named arena: the StageArena rectangle plus the cell
that carries the band's display name (e.g. "Trims Inhouse",
"PPS Submission"). The name typically sits in a horizontally-merged
header cell directly above the arena.

Detection rule: for each StageArena, find the closest horizontal
MergeSpan whose column range overlaps the arena's columns and whose
rows are above (or within the first row of) the arena. The merge
anchor cell's text becomes the band name.

When no MergeSpan above qualifies, fall back to the closest non-merged
string cell directly above the arena's left column.
"""
from __future__ import annotations

from openpyxl.utils import get_column_letter

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import MergeSpan, Rect, StageArena, StageBand, StructureBag


def resolve_stage_bands(canvas: GridCanvas, bag: StructureBag) -> list[StageBand]:
    """Emit one StageBand per StageArena, tagged with its name cell.

    Returns and stores into `bag.stage_bands`.
    """
    bands: list[StageBand] = []
    for arena in bag.stage_arenas:
        name_coord, name_text = _resolve_band_name(canvas, bag, arena)
        if name_coord is None or name_text is None:
            continue
        bands.append(StageBand(
            rect=arena.rect,
            name_coord=name_coord,
            name_text=name_text,
        ))
    bag.stage_bands = bands
    return bands


def _resolve_band_name(canvas: GridCanvas,
                        bag: StructureBag,
                        arena: StageArena) -> tuple[tuple[str, int] | None, str | None]:
    """Return ((column_letter, row_1idx), name_text) or (None, None) if not found."""
    span = _closest_horizontal_merge_above(bag.merge_spans, arena.rect)
    if span is not None:
        anchor_value = _cell_text(canvas, span.rect.r0, span.rect.c0)
        if anchor_value:
            return (get_column_letter(span.rect.c0), span.rect.r0), anchor_value

    # Fallback: closest non-merged string cell directly above arena's left col
    for r in range(arena.rect.r0 - 1, 0, -1):
        text = _cell_text(canvas, r, arena.rect.c0)
        if text:
            return (get_column_letter(arena.rect.c0), r), text

    return None, None


def _closest_horizontal_merge_above(spans: list[MergeSpan], arena_rect: Rect) -> MergeSpan | None:
    """Find the closest horizontal MergeSpan whose columns overlap and rows sit above arena."""
    candidates: list[MergeSpan] = []
    for span in spans:
        if span.orientation != "horizontal":
            continue
        # Must overlap arena's column range
        if span.rect.c1 < arena_rect.c0 or span.rect.c0 > arena_rect.c1:
            continue
        # Must sit at or above arena's top
        if span.rect.r0 >= arena_rect.r0:
            continue
        candidates.append(span)
    if not candidates:
        return None
    # Closest by row distance to arena.r0
    return max(candidates, key=lambda s: s.rect.r0)


def _cell_text(canvas: GridCanvas, row_1idx: int, col_1idx: int) -> str | None:
    """Return stripped text at (row, col) — None if out of bounds or non-string."""
    if not (1 <= row_1idx <= canvas.n_rows and 1 <= col_1idx <= canvas.n_cols):
        return None
    value = canvas.cell_values[row_1idx - 1][col_1idx - 1]
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if text else None
