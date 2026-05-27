"""app.tools.canvas — deterministic primitives over the GridCanvas substrate.

Tools here are stateless, side-effect-free, `@tool`-registered functions
called by pipelines and components. They never invoke the LLM. Each tool
reads a `GridCanvas` (and possibly other typed artifacts) and emits either
new channels written back onto the canvas, typed records, or both.
"""
from __future__ import annotations

from app.tools.canvas.around import (
    CellInfo,
    CellNeighbourhood,
    RangeNeighbourhood,
    build_rich_grid,
    find_around_cell,
    find_around_range,
)
from app.tools.canvas.build import build_canvas

__all__ = [
    "build_canvas",
    "build_rich_grid",
    "find_around_cell",
    "find_around_range",
    "CellInfo",
    "CellNeighbourhood",
    "RangeNeighbourhood",
]
