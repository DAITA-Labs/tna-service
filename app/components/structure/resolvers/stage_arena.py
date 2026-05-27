"""StageArenaResolver — date clusters with plan-marker support → stage arenas.

A StageArena is the rectangular region containing one stage band's
planned-date cells. For ROW_PER_PLI sheets this is a vertical date
column; for SHEET_IS_PLI banded sheets it's a horizontal date row.

Detection rule: a DateStrip qualifies as a StageArena if a
PlanMarkerCluster cell sits within / above / left of the strip's
rectangle (within `max_offset` rows/cols). The "left" check captures
SHEET_IS_PLI anchor patterns where the Plan marker sits at the
leftmost column of a horizontal stage strip.

When no plan markers exist (FA26-style files), the resolver falls
back to BorderedBox neighbourhoods — a date strip wholly inside a
bordered box is also treated as an arena.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import DateStrip, Rect, StageArena, StructureBag


_MAX_PLAN_OFFSET = 3


def resolve_stage_arenas(canvas: GridCanvas,
                          bag: StructureBag,
                          max_plan_offset: int = _MAX_PLAN_OFFSET) -> list[StageArena]:
    """Emit one StageArena per DateStrip with plan-marker or bordered-box support.

    Mutates bag.stage_arenas and returns the same list.
    """
    plan_cells = _collect_plan_marker_cells(bag)
    bordered_rects = [bb.rect for bb in bag.bordered_boxes]

    arenas: list[StageArena] = []
    for strip in bag.date_strips:
        if _strip_has_plan_marker_nearby(strip, plan_cells, max_plan_offset, canvas):
            arenas.append(StageArena(rect=strip.rect))
            continue
        if _strip_inside_bordered_box(strip, bordered_rects):
            arenas.append(StageArena(rect=strip.rect))

    bag.stage_arenas = arenas
    return arenas


def _collect_plan_marker_cells(bag: StructureBag) -> set[tuple[int, int]]:
    """Flatten every PlanMarkerCluster's cells into a single 1-indexed set."""
    cells: set[tuple[int, int]] = set()
    for cluster in bag.plan_marker_clusters:
        for cell in cluster.cells:
            cells.add(cell)
    return cells


def _strip_has_plan_marker_nearby(strip: DateStrip,
                                    plan_cells: set[tuple[int, int]],
                                    max_offset: int,
                                    canvas: GridCanvas) -> bool:
    """Check if any plan marker sits within / above / left of the strip's rect."""
    r0 = max(1, strip.rect.r0 - max_offset)
    r1 = strip.rect.r1
    c0 = max(1, strip.rect.c0 - max_offset)
    c1 = strip.rect.c1

    for (r, c) in plan_cells:
        if r0 <= r <= r1 and c0 <= c <= c1:
            return True
    return False


def _strip_inside_bordered_box(strip: DateStrip, bordered_rects: list[Rect]) -> bool:
    """Check if any BorderedBox contains the strip's rect entirely."""
    for box in bordered_rects:
        if (box.r0 <= strip.rect.r0 and strip.rect.r1 <= box.r1
                and box.c0 <= strip.rect.c0 and strip.rect.c1 <= box.c1):
            return True
    return False
