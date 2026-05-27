"""SubfieldClusterResolver — sub-columns inside each StageBand.

Within a StageBand, sub-columns carry Plan / Actual / Status / Remarks
markers. SubfieldClusterResolver enumerates the columns inside each band's
rect and emits one SubfieldCluster per band carrying the sub-column
coordinates.

The classification of which sub-column carries which canonical
(planned_date vs actual_date vs status) happens later — at field-extraction
time — using the subfield specs in app.specs.subfields. This resolver only
identifies the COLUMN positions.
"""
from __future__ import annotations

from openpyxl.utils import get_column_letter

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import StageBand, StructureBag, SubfieldCluster


def resolve_subfield_clusters(canvas: GridCanvas, bag: StructureBag) -> list[SubfieldCluster]:
    """Emit one SubfieldCluster per StageBand carrying its sub-column coordinates.

    Sub-column coords are (column_letter, anchor_row) tuples where anchor_row
    is the band's header row (the row above the arena's data — typically
    arena.r0 - 1, where sub-labels Plan/Actual/Status sit).
    """
    clusters: list[SubfieldCluster] = []
    for band_idx, band in enumerate(bag.stage_bands):
        sub_coords = _subfield_coords_for_band(canvas, band)
        if not sub_coords:
            continue
        clusters.append(SubfieldCluster(
            parent_band_id=band_idx,
            subfield_coords=tuple(sub_coords),
        ))
    bag.subfield_clusters = clusters
    return clusters


def _subfield_coords_for_band(canvas: GridCanvas, band: StageBand) -> list[tuple[int, int]]:
    """Return (row_1idx, col_1idx) tuples for cells in the band's sub-header row.

    The sub-header row is the row immediately above the band's arena. We
    collect any non-blank cell in that row whose column overlaps the
    band's column range — these are the sub-column labels (Plan, Actual,
    Status, Remarks, etc.).
    """
    sub_row = band.rect.r0 - 1  # row above the arena's top
    if sub_row < 1:
        return []

    coords: list[tuple[int, int]] = []
    for c in range(band.rect.c0, band.rect.c1 + 1):
        if 1 <= sub_row <= canvas.n_rows and 1 <= c <= canvas.n_cols:
            value = canvas.cell_values[sub_row - 1][c - 1]
            if isinstance(value, str) and value.strip():
                coords.append((sub_row, c))
    return coords
