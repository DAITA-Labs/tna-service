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
from app.tools.canvas.dtype_profiles import (
    compute_col_dtype_profiles,
    compute_row_dtype_profiles,
)
from app.tools.canvas.kv_block import find_kv_blocks
from app.tools.canvas.lookups import (
    check_column_has_strip,
    find_merged_cells_in_column,
)
from app.tools.canvas.plan_marker import find_plan_marker_clusters
from app.tools.canvas.repeating_group import find_repeating_row_groups
from app.tools.canvas.scoring import score_column_for_canonical
from app.tools.canvas.strips_date import (
    find_date_strips,
    find_date_strips_horizontal,
    find_date_strips_vertical,
)
from app.tools.canvas.strips_merge import (
    find_merge_spans,
    find_merged_column_strips,
    find_non_merged_strips_horizontal,
    find_non_merged_strips_vertical,
)
from app.tools.canvas.strips_numeric import find_float_strips, find_int_strips
from app.tools.canvas.strips_text import find_long_text_strips, find_same_length_strips
from app.tools.canvas.strips_visual import (
    find_bold_strips,
    find_bold_strips_horizontal,
    find_bold_strips_vertical,
    find_bordered_boxes,
    find_color_strips,
    find_color_strips_horizontal,
    find_color_strips_vertical,
)

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
    # strip detectors — date/numeric/text
    "find_date_strips",
    "find_date_strips_vertical",
    "find_date_strips_horizontal",
    "find_int_strips",
    "find_float_strips",
    "find_same_length_strips",
    "find_long_text_strips",
    # strip detectors — visual
    "find_color_strips",
    "find_color_strips_horizontal",
    "find_color_strips_vertical",
    "find_bold_strips",
    "find_bold_strips_horizontal",
    "find_bold_strips_vertical",
    "find_bordered_boxes",
    # strip detectors — merge
    "find_merge_spans",
    "find_non_merged_strips_vertical",
    "find_non_merged_strips_horizontal",
    "find_merged_column_strips",
    # block + group detectors
    "find_kv_blocks",
    "find_repeating_row_groups",
    "find_plan_marker_clusters",
    # dtype profile aggregators
    "compute_row_dtype_profiles",
    "compute_col_dtype_profiles",
    # column/cell lookups used by field extractors
    "check_column_has_strip",
    "find_merged_cells_in_column",
    "score_column_for_canonical",
]
