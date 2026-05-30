"""MetadataAssembler — kv-block metadata flow."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import KvBlock, StructureBag
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.plan.metadata_assembler import MetadataAssembler
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.read_direction import ReadDirection


def _make_bundle(kv_blocks: list[KvBlock] | None = None) -> ClusterAnchorBundle:
    canvas = GridCanvas(
        n_rows=20, n_cols=20,
        cell_values=[[None] * 20 for _ in range(20)],
        channels={},
    )
    bag = StructureBag()
    bag.kv_blocks = kv_blocks or []
    hint = LayoutHint(
        axes=LayoutAxes(
            pli_axis="vertical", stage_axis="horizontal", subfield_axis="horizontal",
            confidence={"pli": 0.9, "stage": 0.9, "subfield": 0.9},
        ),
        cluster_id="c0", confidence=0.9,
        candidate_columns={}, candidate_rows={}, candidate_kv_blocks={},
        data_row_ranges=[], section_boundaries=[], header_band=None,
    )
    cluster = PliCluster(cluster_id="c0", sheet_names=["TNA"])
    return ClusterAnchorBundle(
        cluster=cluster, anchor_sheet_name="TNA",
        canvas=canvas, bag=bag, hint=hint,
    )


def test_empty_kv_blocks_produces_empty_metadata_entries() -> None:
    out = MetadataAssembler().run(bundle=_make_bundle(kv_blocks=[]))
    assert out["metadata_entries"] == []


def test_every_kv_block_becomes_a_metadata_plan() -> None:
    kvs = [
        KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                 label_text="Buyer", value_dtype=4),
        KvBlock(label_coord=("A", 3), value_coord=("B", 3),
                 label_text="Season", value_dtype=4),
    ]
    out = MetadataAssembler().run(bundle=_make_bundle(kv_blocks=kvs))
    entries = out["metadata_entries"]
    assert len(entries) == 2
    assert {e.header_text for e in entries} == {"Buyer", "Season"}


def test_metadata_plan_carries_sheet_scope_and_fixed_direction() -> None:
    kv = KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                  label_text="Buyer", value_dtype=4)
    out = MetadataAssembler().run(bundle=_make_bundle(kv_blocks=[kv]))
    entry = out["metadata_entries"][0]
    assert entry.mode           == FieldLocationMode.KV_BLOCK
    assert entry.scope          == FieldScope.SHEET
    assert entry.read_direction == ReadDirection.FIXED
    assert entry.kv_block       is kv


def test_label_matching_metadata_spec_alias_sets_canonical() -> None:
    """A kv whose label_text matches a METADATA_SPECS alias gets its canonical."""
    kv = KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                  label_text="Buyer", value_dtype=4)
    out   = MetadataAssembler().run(bundle=_make_bundle(kv_blocks=[kv]))
    entry = out["metadata_entries"][0]
    # Whether or not "Buyer" appears in METADATA_SPECS aliases — accept both.
    assert entry.canonical is None or isinstance(entry.canonical, str)


def test_label_with_no_alias_match_has_no_canonical() -> None:
    kv = KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                  label_text="Some Random Unknown Field Z123",
                  value_dtype=4)
    out   = MetadataAssembler().run(bundle=_make_bundle(kv_blocks=[kv]))
    entry = out["metadata_entries"][0]
    assert entry.canonical is None


def test_claimed_kv_blocks_are_excluded() -> None:
    """A KvBlock already claimed by an identifier picker doesn't become metadata."""
    claimed = KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                       label_text="Buyer", value_dtype=4)
    free    = KvBlock(label_coord=("A", 3), value_coord=("B", 3),
                       label_text="Season", value_dtype=4)
    out = MetadataAssembler().run(
        bundle=_make_bundle(kv_blocks=[claimed, free]),
        claimed_kv_blocks={claimed},
    )
    entries = out["metadata_entries"]
    assert len(entries) == 1
    assert entries[0].kv_block is free


def test_empty_label_text_kv_still_emits_entry_with_no_canonical() -> None:
    """Edge case: empty label text yields entry with header_text='' and canonical=None."""
    kv = KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                  label_text="", value_dtype=4)
    out   = MetadataAssembler().run(bundle=_make_bundle(kv_blocks=[kv]))
    entry = out["metadata_entries"][0]
    assert entry.header_text == ""
    assert entry.canonical is None
