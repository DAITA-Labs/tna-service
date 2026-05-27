"""PlanMarkerCluster detector — flood-fill grouping of plan-marker cells."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.artifacts.structure import PlanMarkerCluster
from app.tools.canvas.build import build_canvas
from app.tools.canvas.plan_marker import find_plan_marker_clusters


DATASET = Path(__file__).resolve().parents[4] / "dataset"


@pytest.fixture
def dkn_canvas():
    """DKN has 'Plan' / 'Planned' header cells under each stage band."""
    wb = load_workbook(DATASET / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
                       data_only=True)
    return build_canvas(wb.active)


def test_clusters_returned_as_records(dkn_canvas) -> None:
    """find_plan_marker_clusters returns PlanMarkerCluster records."""
    clusters = find_plan_marker_clusters(dkn_canvas)
    assert isinstance(clusters, list)
    assert all(isinstance(c, PlanMarkerCluster) for c in clusters)


def test_each_cluster_has_at_least_one_cell(dkn_canvas) -> None:
    """A PlanMarkerCluster always carries ≥1 cell coordinate."""
    for c in find_plan_marker_clusters(dkn_canvas):
        assert len(c.cells) >= 1


def test_cells_are_1_indexed(dkn_canvas) -> None:
    """Cell coordinates are 1-indexed tuples matching the sheet's row/col numbers."""
    for cluster in find_plan_marker_clusters(dkn_canvas):
        for (r, col) in cluster.cells:
            assert r >= 1
            assert col >= 1


def test_clusters_do_not_overlap(dkn_canvas) -> None:
    """Each cell appears in at most one cluster (flood fill is exhaustive)."""
    seen: set[tuple[int, int]] = set()
    for cluster in find_plan_marker_clusters(dkn_canvas):
        for cell in cluster.cells:
            assert cell not in seen
            seen.add(cell)


def test_flood_fill_groups_adjacent_cells() -> None:
    """Internal flood-fill helper groups 4-connected cells."""
    from app.tools.canvas.plan_marker import _flood_fill_plan_marker

    # 2×2 block of plan markers
    channel = [
        [1, 1, 0],
        [1, 1, 0],
        [0, 0, 0],
    ]
    visited: set[tuple[int, int]] = set()
    group = _flood_fill_plan_marker(channel, 0, 0, 3, 3, visited)
    assert sorted(group) == [(0, 0), (0, 1), (1, 0), (1, 1)]


def test_tool_registered() -> None:
    from app.tools._registry import TOOL_REGISTRY

    assert "find_plan_marker_clusters" in TOOL_REGISTRY.names()
