"""SubfieldClusterResolver — sub-column coords for each StageBand."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import Rect, StageBand, StructureBag, SubfieldCluster
from app.components.structure.resolvers.subfield_cluster import resolve_subfield_clusters


def _canvas_with_subheaders(*subheaders: tuple[int, int, str]):
    """Build a canvas with each (row, col, text) installed; 1-indexed."""
    cells = [[None] * 30 for _ in range(20)]
    for r, c, text in subheaders:
        cells[r - 1][c - 1] = text
    return GridCanvas(n_rows=20, n_cols=30, cell_values=cells)


def test_no_bands_means_no_clusters() -> None:
    """An empty stage_bands list produces an empty subfield_clusters list."""
    canvas = _canvas_with_subheaders()
    bag = StructureBag()
    clusters = resolve_subfield_clusters(canvas, bag)
    assert clusters == []


def test_subfield_row_above_arena_collected() -> None:
    """Cells in band.r0-1 row with non-empty string content become subfield coords."""
    canvas = _canvas_with_subheaders(
        (3, 14, "Plan"),
        (3, 15, "Actual"),
        (3, 16, "Status"),
    )
    bag = StructureBag()
    bag.stage_bands = [StageBand(
        rect=Rect(4, 14, 43, 16),
        name_coord=("N", 2),
        name_text="PPS",
    )]

    clusters = resolve_subfield_clusters(canvas, bag)
    assert len(clusters) == 1
    coords = clusters[0].subfield_coords
    assert (3, 14) in coords
    assert (3, 15) in coords
    assert (3, 16) in coords


def test_parent_band_id_indexes_into_bag() -> None:
    """SubfieldCluster.parent_band_id is the band's index in bag.stage_bands."""
    canvas = _canvas_with_subheaders((3, 14, "Plan"))
    bag = StructureBag()
    bag.stage_bands = [
        StageBand(rect=Rect(4, 14, 43, 14), name_coord=("N", 2), name_text="A"),
    ]
    clusters = resolve_subfield_clusters(canvas, bag)
    assert clusters[0].parent_band_id == 0


def test_band_with_no_subheaders_skipped() -> None:
    """A band whose sub-header row is entirely blank produces no cluster."""
    canvas = _canvas_with_subheaders()  # no cells installed
    bag = StructureBag()
    bag.stage_bands = [StageBand(rect=Rect(4, 14, 43, 14),
                                  name_coord=("N", 2),
                                  name_text="X")]
    clusters = resolve_subfield_clusters(canvas, bag)
    assert clusters == []
