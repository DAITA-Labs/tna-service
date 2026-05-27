"""GridCanvas — spatial substrate for canvas-based extraction.

A `GridCanvas` is a 2D substrate carrying per-cell measurements as named
channels. Each channel is an n_rows × n_cols matrix indexed in the same
coordinate space as the source sheet (1-indexed externally, 0-indexed in
the matrices). Tools and components write derived channels back onto the
canvas while also emitting typed records for iteration.

The canvas is the shared spatial vocabulary every layer of the canvas
architecture reads from and writes to. Channels are raw measurements
(dtype, fill_color, merge_shape, ...); typed records (DateStrip, HeaderBand,
StageArena, Finding) carry semantic meaning derived from those channels.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GridCanvas:
    """A 2D measurement substrate over one sheet of an Excel workbook.

    Attributes:
        n_rows / n_cols: sheet dimensions, used by every consumer.
        cell_values:     raw per-cell values (merge-resolved at build time).
        channels:        named per-cell measurement matrices keyed by name.
        merge_ranges:    canonical merge ranges as (r0, c0, r1, c1) tuples,
                          1-indexed inclusive.
    """

    n_rows:       int
    n_cols:       int
    cell_values:  list[list[Any]]
    channels:     dict[str, list[list[int]]] = field(default_factory=dict)
    merge_ranges: set[tuple[int, int, int, int]] = field(default_factory=set)

    def add_channel(self, name: str, matrix: list[list[int]]) -> None:
        """Install a new channel under `name`. Caller owns shape correctness."""
        self.channels[name] = matrix
