from app.models.artifacts import SheetSignals, RowSpec, KVAnchor
from app.enums.row_role import RowRole
from app.services.planner.block_segmenter import segment_blocks


def test_segment_two_blocks_separated_by_blank_run():
    rows = [
        RowSpec(idx=1, role=RowRole.TITLE),
        RowSpec(idx=4, role=RowRole.ANCHOR, group_id=0),
        RowSpec(idx=7, role=RowRole.BLANK),
        RowSpec(idx=8, role=RowRole.BLANK),
        RowSpec(idx=9, role=RowRole.ANCHOR, group_id=1),
        RowSpec(idx=12, role=RowRole.BLANK),
    ]
    kvs = [
        KVAnchor(label_cell="A4", value_cell="B4", field="io_number"),
        KVAnchor(label_cell="A9", value_cell="B9", field="io_number"),
    ]
    blocks = segment_blocks(rows, kvs, blank_run_gaps=[(7, 8), (12, 12)])
    assert len(blocks) == 2
    assert blocks[0].bbox == (4, 6)
    assert blocks[1].bbox == (9, 11)


def test_segment_no_blocks_when_no_anchors():
    blocks = segment_blocks([], [], [])
    assert blocks == []
