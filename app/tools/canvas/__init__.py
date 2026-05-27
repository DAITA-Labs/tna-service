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
from app.tools.canvas.query import (
    SpecMatch,
    aggregate_by_col,
    aggregate_by_row,
    all_specs,
    find_field_label_cells,
    find_header_rows_via_specs,
    query_all,
    query_phase,
    query_spec,
    spec_summary,
    specs_for_phase,
    text_dense_cols,
    text_dense_rows,
)
from app.tools.canvas.strips_date import (
    find_date_strips,
    find_date_strips_horizontal,
    find_date_strips_vertical,
)
from app.tools.canvas.strips_numeric import find_float_strips, find_int_strips
from app.tools.canvas.strips_text import find_long_text_strips, find_same_length_strips

__all__ = [
    # build
    "build_canvas",
    # around
    "build_rich_grid",
    "find_around_cell",
    "find_around_range",
    "CellInfo",
    "CellNeighbourhood",
    "RangeNeighbourhood",
    # query
    "SpecMatch",
    "all_specs",
    "specs_for_phase",
    "text_dense_rows",
    "text_dense_cols",
    "query_spec",
    "query_phase",
    "query_all",
    "aggregate_by_row",
    "aggregate_by_col",
    "find_header_rows_via_specs",
    "find_field_label_cells",
    "spec_summary",
    # strip detectors
    "find_date_strips",
    "find_date_strips_vertical",
    "find_date_strips_horizontal",
    "find_int_strips",
    "find_float_strips",
    "find_same_length_strips",
    "find_long_text_strips",
]
