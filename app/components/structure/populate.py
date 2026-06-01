"""Bag populators — wire strip detectors and resolvers onto a StructureBag.

Two helpers, each consuming a `(canvas, bag)` pair and appending records:

  `populate_patterns`  — fans every strip detector into the bag's
                         pattern-record fields (date / int / float / text /
                         color / bold / borders / merges / kv / repeating /
                         plan markers). No semantic reasoning.

  `populate_semantics` — runs the six structural resolvers in dependency
                         order (header_band → data_row_range → stage_arena
                         → stage_band → subfield_cluster →
                         section_boundary), each reading pattern records
                         and writing semantic records back to the bag.

The split lets `run_structure_phase` stay declarative and lets tests
exercise either half in isolation.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import StructureBag
from app.components.structure.resolvers import (
    resolve_data_row_ranges,
    resolve_header_band,
    resolve_section_boundaries,
    resolve_stage_arenas,
    resolve_stage_bands,
    resolve_subfield_clusters,
)
from app.tools.canvas.kv_block import find_kv_blocks
from app.tools.canvas.plan_marker import find_plan_marker_clusters
from app.tools.canvas.repeating_group import find_repeating_row_groups
from app.tools.canvas.strips_date import find_date_strips
from app.tools.canvas.strips_merge import (
    find_merge_spans,
    find_merged_column_strips,
    find_non_merged_strips_horizontal,
    find_non_merged_strips_vertical,
)
from app.tools.canvas.strips_numeric import find_float_strips, find_int_strips
from app.tools.canvas.strips_text import (
    find_long_text_strips,
    find_same_length_strips,
)
from app.tools.canvas.strips_visual import (
    find_bold_strips,
    find_bordered_boxes,
    find_color_strips,
)


def populate_patterns(canvas: GridCanvas, bag: StructureBag) -> None:
    """Run every strip detector and append results to `bag`."""
    bag.date_strips.extend(find_date_strips(canvas))
    bag.int_strips.extend(find_int_strips(canvas))
    bag.float_strips.extend(find_float_strips(canvas))
    bag.same_length_strips.extend(find_same_length_strips(canvas))
    bag.long_text_strips.extend(find_long_text_strips(canvas))
    bag.color_strips.extend(find_color_strips(canvas))
    bag.bold_strips.extend(find_bold_strips(canvas))
    bag.bordered_boxes.extend(find_bordered_boxes(canvas))
    bag.merge_spans.extend(find_merge_spans(canvas))
    bag.non_merged_strips.extend(find_non_merged_strips_vertical(canvas))
    bag.non_merged_strips.extend(find_non_merged_strips_horizontal(canvas))
    bag.merged_column_strips.extend(find_merged_column_strips(canvas))
    bag.kv_blocks.extend(find_kv_blocks(canvas))
    bag.repeating_groups.extend(find_repeating_row_groups(canvas))
    bag.plan_marker_clusters.extend(find_plan_marker_clusters(canvas))


def populate_semantics(canvas: GridCanvas, bag: StructureBag) -> None:
    """Run the six structural resolvers in dependency order.

    Each resolver both returns its records and mutates the bag, so the
    caller can chain them through the bag without manual plumbing.
    """
    resolve_header_band(canvas, bag)
    _refine_numeric_strips_after_header(canvas, bag)
    resolve_data_row_ranges(canvas, bag)
    resolve_stage_arenas(canvas, bag)
    resolve_stage_bands(canvas, bag)
    resolve_subfield_clusters(canvas, bag)
    resolve_section_boundaries(canvas, bag)


def _refine_numeric_strips_after_header(canvas: GridCanvas, bag: StructureBag) -> None:
    """Re-detect int/float strips below the header band.

    `populate_patterns` runs before the header band is known, so density
    on a real quantity column is dragged below threshold by title +
    sub-header strings sitting above the data. Once `resolve_header_band`
    fixes the band rect, re-run the detectors with `data_row_start` past
    the header and replace the bag entries — header pollution removed.

    No-op when no header band was detected.
    """
    if bag.header_band is None:
        return
    data_row_start = bag.header_band.rect.r1 + 1
    bag.int_strips   = find_int_strips(canvas, data_row_start=data_row_start)
    bag.float_strips = find_float_strips(canvas, data_row_start=data_row_start)
