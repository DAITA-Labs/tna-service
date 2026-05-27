"""StageArenaResolver — DateStrip + PlanMarker (or BorderedBox) → arenas."""
from __future__ import annotations

from app.artifacts.structure import (
    BorderedBox,
    DateStrip,
    PlanMarkerCluster,
    Rect,
    StageArena,
    StructureBag,
)
from app.components.structure.resolvers.stage_arena import resolve_stage_arenas


def _make_canvas(n_rows: int = 50, n_cols: int = 30):
    """Minimal canvas stub for resolver tests (no channels needed by this resolver)."""
    from app.artifacts.canvas import GridCanvas
    return GridCanvas(
        n_rows=n_rows, n_cols=n_cols,
        cell_values=[[None] * n_cols for _ in range(n_rows)],
        channels={},
        merge_ranges=set(),
    )


def test_date_strip_with_nearby_plan_marker_becomes_arena() -> None:
    """A DateStrip with a PlanMarker within max_offset above becomes a StageArena."""
    canvas = _make_canvas()
    bag = StructureBag()
    bag.date_strips = [DateStrip(rect=Rect(4, 14, 43, 14), orientation="vertical", density=1.0)]
    bag.plan_marker_clusters = [PlanMarkerCluster(cells=((3, 14),))]  # 1 row above the strip

    arenas = resolve_stage_arenas(canvas, bag)
    assert len(arenas) == 1
    assert arenas[0].rect == Rect(4, 14, 43, 14)


def test_date_strip_without_plan_marker_skipped() -> None:
    """A DateStrip with no plan marker nearby produces no arena."""
    canvas = _make_canvas()
    bag = StructureBag()
    bag.date_strips = [DateStrip(rect=Rect(4, 14, 43, 14), orientation="vertical", density=1.0)]
    # No plan markers, no bordered boxes

    arenas = resolve_stage_arenas(canvas, bag)
    assert arenas == []


def test_bordered_box_fallback_when_no_plan_marker() -> None:
    """A DateStrip wholly inside a BorderedBox qualifies even without plan markers."""
    canvas = _make_canvas()
    bag = StructureBag()
    bag.date_strips = [DateStrip(rect=Rect(5, 15, 10, 15), orientation="vertical", density=1.0)]
    bag.bordered_boxes = [BorderedBox(rect=Rect(4, 14, 11, 16))]  # contains the strip

    arenas = resolve_stage_arenas(canvas, bag)
    assert len(arenas) == 1


def test_plan_marker_to_left_qualifies_strip() -> None:
    """The SHEET_IS_PLI pattern: plan marker LEFT of a horizontal strip."""
    canvas = _make_canvas()
    bag = StructureBag()
    # Horizontal date strip on row 9, cols 5-15
    bag.date_strips = [DateStrip(rect=Rect(9, 5, 9, 15), orientation="horizontal", density=1.0)]
    # Plan marker at (9, 4) — directly to the left of the strip
    bag.plan_marker_clusters = [PlanMarkerCluster(cells=((9, 4),))]

    arenas = resolve_stage_arenas(canvas, bag, max_plan_offset=3)
    assert len(arenas) == 1


def test_plan_marker_too_far_does_not_qualify() -> None:
    """A plan marker beyond max_plan_offset cells away does not trigger arena."""
    canvas = _make_canvas()
    bag = StructureBag()
    bag.date_strips = [DateStrip(rect=Rect(4, 14, 43, 14), orientation="vertical", density=1.0)]
    bag.plan_marker_clusters = [PlanMarkerCluster(cells=((50, 50),))]  # very far away

    arenas = resolve_stage_arenas(canvas, bag, max_plan_offset=3)
    assert arenas == []


def test_idempotent() -> None:
    """Calling resolver twice yields same arenas."""
    canvas = _make_canvas()
    bag = StructureBag()
    bag.date_strips = [DateStrip(rect=Rect(4, 14, 43, 14), orientation="vertical", density=1.0)]
    bag.plan_marker_clusters = [PlanMarkerCluster(cells=((3, 14),))]

    arenas_a = resolve_stage_arenas(canvas, bag)
    arenas_b = resolve_stage_arenas(canvas, bag)
    assert [a.rect for a in arenas_a] == [a.rect for a in arenas_b]
