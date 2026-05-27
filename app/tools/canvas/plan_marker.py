"""PlanMarkerCluster detector — groups of cells matching 'Plan'/'Planned'/'Scheduled'.

The `plan_marker` channel populated by `build_canvas` marks each cell as
1 if its text contains a plan-marker token (case-insensitive), 0 otherwise.
This detector groups adjacent plan-marker cells (4-connectivity) into
PlanMarkerCluster records — one per connected group.

A PlanMarkerCluster is the canonical anchor for StageArenaResolver: any
date cluster (DateStrip) with at least one plan marker in its
neighbourhood (within / above / left of the rectangle) qualifies as a
stage arena. Without plan markers, arena detection falls back to
BorderedBox or ColorStrip cues.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import PlanMarkerCluster
from app.tools._decorator import tool


@tool("find_plan_marker_clusters")
def find_plan_marker_clusters(canvas: GridCanvas) -> list[PlanMarkerCluster]:
    """Group adjacent plan-marker cells (4-connectivity) into clusters.

    Each PlanMarkerCluster carries the set of 1-indexed (row, col) cells
    in the group. A cluster of size 1 is emitted only if the cell is
    truly isolated; usually plan markers cluster in pairs or triples
    (PLAN / RECVD / APPD sub-header trios).
    """
    channel = canvas.channels.get("plan_marker")
    if channel is None:
        return []

    visited: set[tuple[int, int]] = set()
    clusters: list[PlanMarkerCluster] = []

    for r in range(canvas.n_rows):
        for c in range(canvas.n_cols):
            if channel[r][c] != 1 or (r, c) in visited:
                continue
            group = _flood_fill_plan_marker(channel, r, c, canvas.n_rows, canvas.n_cols, visited)
            if not group:
                continue
            cells_1idx = tuple(sorted((rr + 1, cc + 1) for rr, cc in group))
            clusters.append(PlanMarkerCluster(cells=cells_1idx))
    return clusters


def _flood_fill_plan_marker(channel: list[list[int]],
                             start_r: int,
                             start_c: int,
                             n_rows: int,
                             n_cols: int,
                             visited: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """4-connectivity flood fill — return all 0-indexed cells in the connected group."""
    group: list[tuple[int, int]] = []
    stack: list[tuple[int, int]] = [(start_r, start_c)]
    while stack:
        r, c = stack.pop()
        if (r, c) in visited:
            continue
        if not (0 <= r < n_rows and 0 <= c < n_cols):
            continue
        if channel[r][c] != 1:
            continue
        visited.add((r, c))
        group.append((r, c))
        stack.extend([(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)])
    return group
