"""GridCanvas artifact construction and channel installation."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas


def test_empty_canvas_constructs() -> None:
    """A GridCanvas with empty channels and a 3x3 cell_values constructs cleanly."""
    canvas = GridCanvas(
        n_rows=3,
        n_cols=3,
        cell_values=[[None] * 3 for _ in range(3)],
    )
    assert canvas.n_rows == 3
    assert canvas.n_cols == 3
    assert canvas.channels == {}
    assert canvas.merge_ranges == set()


def test_add_channel_installs_matrix() -> None:
    """add_channel must store the matrix under the given name."""
    canvas = GridCanvas(n_rows=2, n_cols=2, cell_values=[[None] * 2 for _ in range(2)])
    canvas.add_channel("dtype", [[0, 0], [0, 0]])

    assert "dtype" in canvas.channels
    assert canvas.channels["dtype"] == [[0, 0], [0, 0]]


def test_merge_ranges_preserved() -> None:
    """Merge ranges are tuples of (r0, c0, r1, c1), 1-indexed inclusive."""
    merges = {(2, 3, 4, 5), (1, 1, 1, 3)}
    canvas = GridCanvas(
        n_rows=10,
        n_cols=10,
        cell_values=[[None] * 10 for _ in range(10)],
        merge_ranges=merges,
    )

    assert canvas.merge_ranges == merges
    assert (2, 3, 4, 5) in canvas.merge_ranges
