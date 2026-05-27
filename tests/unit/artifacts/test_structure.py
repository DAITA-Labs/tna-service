"""Structure artifact records and StructureBag carrier."""
from __future__ import annotations

from app.artifacts.structure import (
    BoldStrip,
    BorderedBox,
    ColorStrip,
    DataRowRange,
    DateStrip,
    FloatStrip,
    HeaderBand,
    IntStrip,
    KvBlock,
    LongTextStrip,
    MergeSpan,
    MergedColumnStrip,
    NonMergedStrip,
    PlanMarkerCluster,
    Rect,
    RepeatingRowGroup,
    SameLengthStrip,
    SectionBoundary,
    StageArena,
    StageBand,
    StructureBag,
    SubfieldCluster,
)


def test_rect_area() -> None:
    """Rect.area returns inclusive-inclusive cell count."""
    rect = Rect(r0=2, c0=3, r1=4, c1=5)
    # rows 2..4 = 3, cols 3..5 = 3 → 9 cells
    assert rect.area == 9


def test_rect_single_cell() -> None:
    """A 1x1 Rect has area 1."""
    assert Rect(r0=1, c0=1, r1=1, c1=1).area == 1


def test_empty_bag_has_empty_collections() -> None:
    """A fresh StructureBag has empty lists for every record type."""
    bag = StructureBag()
    assert bag.date_strips == []
    assert bag.int_strips == []
    assert bag.color_strips == []
    assert bag.merge_spans == []
    assert bag.kv_blocks == []
    assert bag.repeating_groups == []
    assert bag.header_band is None
    assert bag.stage_arenas == []


def test_date_strip_carries_orientation() -> None:
    """DateStrip stores rect + orientation + density."""
    strip = DateStrip(rect=Rect(4, 14, 43, 14), orientation="vertical", density=0.95)

    assert strip.orientation == "vertical"
    assert strip.density == 0.95


def test_int_strip_magnitude_tagged() -> None:
    """IntStrip carries magnitude so quantity can distinguish from size cols."""
    strip = IntStrip(rect=Rect(4, 13, 43, 13), magnitude="large", density=0.92)

    assert strip.magnitude == "large"


def test_kv_block_pairs_label_with_value() -> None:
    """KvBlock stores label and value coords plus the label text."""
    kv = KvBlock(
        label_coord=("A", 4),
        value_coord=("B", 4),
        label_text="Job No",
        value_dtype=2,
    )

    assert kv.label_coord == ("A", 4)
    assert kv.label_text == "Job No"


def test_repeating_row_group_signature() -> None:
    """RepeatingRowGroup carries an indexed tuple plus a signature."""
    grp = RepeatingRowGroup(row_indices=(1, 7, 14, 28), signature="abc123")
    assert len(grp.row_indices) == 4
    assert grp.signature == "abc123"


def test_semantic_records_attach_to_bag() -> None:
    """Resolvers can write semantic records back to the bag."""
    bag = StructureBag()
    bag.header_band = HeaderBand(rect=Rect(1, 1, 2, 10), score=63.45)
    bag.stage_arenas.append(StageArena(rect=Rect(4, 14, 43, 18)))
    bag.data_row_ranges.append(DataRowRange(row_start=3, row_end=42))

    assert bag.header_band is not None
    assert bag.header_band.score == 63.45
    assert len(bag.stage_arenas) == 1
    assert bag.data_row_ranges[0].row_end == 42


def test_all_pattern_types_constructable() -> None:
    """All pattern dataclasses construct with minimal kwargs."""
    r = Rect(1, 1, 1, 1)
    # Just verify each type instantiates; semantic value not under test.
    FloatStrip(rect=r, density=0.5)
    SameLengthStrip(rect=r, length=6, density=0.8)
    LongTextStrip(rect=r, mean_length=30.0)
    ColorStrip(rect=r, orientation="horizontal", color="FFFF00")
    BoldStrip(rect=r, orientation="horizontal")
    BorderedBox(rect=r)
    MergeSpan(rect=r, orientation="horizontal")
    NonMergedStrip(rect=r, orientation="vertical")
    MergedColumnStrip(rect=r, merge_count=2)
    PlanMarkerCluster(cells=((4, 14), (4, 17)))
    SectionBoundary(start_row=1, end_row=6, section_id="s0")
    StageBand(rect=r, name_coord=("O", 2), name_text="Trims Inhouse")
    SubfieldCluster(parent_band_id=0, subfield_coords=(("R", 3), ("S", 3)))
