"""find_around_cell + find_around_range neighbourhood primitives."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.tools.canvas.around import (
    CellInfo,
    CellNeighbourhood,
    build_rich_grid,
    find_around_cell,
    find_around_range,
)


DATASET = Path(__file__).resolve().parents[4] / "dataset"


@pytest.fixture
def dkn_grid() -> dict:
    """A rich grid over the DKN baseline xlsx."""
    wb = load_workbook(DATASET / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
                       data_only=True)
    return build_rich_grid(wb.active)


def test_build_rich_grid_returns_dict(dkn_grid: dict) -> None:
    """build_rich_grid returns a dict keyed by (row, col_letter)."""
    assert isinstance(dkn_grid, dict)
    assert len(dkn_grid) > 0
    sample_key = next(iter(dkn_grid))
    assert isinstance(sample_key, tuple)
    assert len(sample_key) == 2
    assert isinstance(sample_key[0], int)
    assert isinstance(sample_key[1], str)


def test_cell_info_has_required_fields(dkn_grid: dict) -> None:
    """Every CellInfo carries dtype, merge metadata, and style hints."""
    info = next(iter(dkn_grid.values()))
    assert isinstance(info, CellInfo)
    assert hasattr(info, "coord")
    assert hasattr(info, "dtype")
    assert hasattr(info, "is_merged")
    assert hasattr(info, "merge_anchor")
    assert hasattr(info, "is_bold")


def test_find_around_cell_returns_neighbourhood(dkn_grid: dict) -> None:
    """find_around_cell returns a CellNeighbourhood with all 8 neighbours + center."""
    nb = find_around_cell(dkn_grid, "B4")
    assert isinstance(nb, CellNeighbourhood)
    assert nb.center.coord == "B4"
    # All 8 attributes exist (some may be None at sheet edges)
    for attr in ("above", "below", "left", "right",
                 "above_left", "above_right", "below_left", "below_right"):
        assert hasattr(nb, attr)


def test_find_around_cell_neighbours_have_right_coords(dkn_grid: dict) -> None:
    """A center at C5 has B5 to its left and D5 to its right."""
    nb = find_around_cell(dkn_grid, "C5")
    if nb.left is not None:
        assert nb.left.coord == "B5"
    if nb.right is not None:
        assert nb.right.coord == "D5"
    if nb.above is not None:
        assert nb.above.coord == "C4"


def test_find_around_range_inside_summary(dkn_grid: dict) -> None:
    """find_around_range returns inside_summary with dtype distribution + density."""
    nb = find_around_range(dkn_grid, row_range=(4, 6), col_range=("K", "L"))
    assert nb.range_coord == "K4:L6"
    assert "total_cells" in nb.inside_summary
    assert "density" in nb.inside_summary
    assert nb.inside_summary["total_cells"] >= 0


def test_tools_registered() -> None:
    """All three @tool-decorated entry points are registered."""
    from app.tools._registry import TOOL_REGISTRY

    names = TOOL_REGISTRY.names()
    assert "build_rich_grid" in names
    assert "find_around_cell" in names
    assert "find_around_range" in names
