"""Segment a sheet into PliBlocks for SECTION_PER_PLI layouts.

Each block is bounded by blank-run gaps. Identity (KV anchors falling inside
the block's bbox) and stage bands (also inside the bbox) are attached.
"""
from __future__ import annotations

from openpyxl.utils.cell import coordinate_from_string

from app.core.logs import get_logger
from app.enums.row_role import RowRole
from app.models.artifacts import KVAnchor, PliBlock, RowSpec, StageBandSpec

log = get_logger(__name__)


def _row_of(addr: str) -> int:
    """Return the 1-based row index from a cell address string."""
    _, r = coordinate_from_string(addr)
    return r


def segment_blocks(
    rows: list[RowSpec],
    kv_anchors: list[KVAnchor],
    blank_run_gaps: list[tuple[int, int]],
    stage_bands: list[StageBandSpec] | None = None,
) -> list[PliBlock]:
    """Segment ANCHOR rows into PliBlocks, clipping each at the next blank gap.

    Returns one PliBlock per ANCHOR row, with KV anchors and stage bands
    whose name cells fall within the block's row range attached.
    """
    stage_bands = stage_bands or []
    anchors = [r for r in rows if r.role is RowRole.ANCHOR]
    if not anchors:
        return []

    sorted_gaps = sorted(blank_run_gaps)
    blocks: list[PliBlock] = []
    block_id = 0
    for i, anc in enumerate(anchors):
        start = anc.idx
        end = anchors[i + 1].idx - 1 if i + 1 < len(anchors) else None
        for g_start, g_end in sorted_gaps:
            if g_start >= start and (end is None or g_start <= end):
                end = g_start - 1
                break
        if end is None:
            end = start

        block_kvs = [
            kv for kv in kv_anchors
            if start <= _row_of(kv.label_cell) <= end
        ]
        block_bands = [
            sb for sb in stage_bands
            if start <= _row_of(sb.name_cell) <= end
        ]
        blocks.append(PliBlock(
            id=block_id, bbox=(start, end),
            identity=block_kvs, stage_bands=block_bands,
        ))
        block_id += 1
    log.info("blocks_segmented", count=len(blocks))
    return blocks
