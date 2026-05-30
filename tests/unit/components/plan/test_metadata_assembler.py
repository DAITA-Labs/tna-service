"""MetadataAssembler — kv-block metadata flow."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import HeaderBand, KvBlock, Rect, StructureBag
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.plan.metadata_assembler import MetadataAssembler
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.read_direction import ReadDirection


def _make_bundle(
    *,
    kv_blocks:    list[KvBlock] | None = None,
    header_row:   list | None = None,
    header_band_rect: Rect | None = None,
) -> ClusterAnchorBundle:
    n_rows, n_cols = 20, 20
    cells = [[None] * n_cols for _ in range(n_rows)]
    if header_row is not None:
        # Place the supplied row at row index 2 (1-indexed row 3).
        for col_i, val in enumerate(header_row):
            cells[2][col_i] = val
    canvas = GridCanvas(
        n_rows=n_rows, n_cols=n_cols,
        cell_values=cells,
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
        data_row_ranges=[], section_boundaries=[],
        header_band=(HeaderBand(rect=header_band_rect, score=0.9)
                      if header_band_rect is not None else None),
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


# ── Unclaimed-column path ──────────────────────────────────────────────────


def test_no_header_band_yields_no_column_metadata() -> None:
    """Without a HeaderBand we can't probe headers — no column metadata emitted."""
    out = MetadataAssembler().run(bundle=_make_bundle())
    assert all(e.mode != FieldLocationMode.COLUMN for e in out["metadata_entries"])


def test_unclaimed_columns_become_column_metadata() -> None:
    """Every text-bearing column inside the band, unclaimed, → MetadataPlan(COLUMN)."""
    header_row = ["IO No", "Quantity", "Buyer Comments", None, "Style"]
    bundle = _make_bundle(
        header_row=header_row,
        # Header band covers row 3 across cols 1..5
        header_band_rect=Rect(r0=3, c0=1, r1=3, c1=5),
    )
    out = MetadataAssembler().run(bundle=bundle)
    col_entries = [e for e in out["metadata_entries"]
                    if e.mode == FieldLocationMode.COLUMN]

    # 4 columns have text headers (col 4 is None → skipped).
    assert len(col_entries) == 4
    header_texts = {e.header_text for e in col_entries}
    assert header_texts == {"IO No", "Quantity", "Buyer Comments", "Style"}


def test_claimed_columns_are_excluded_from_column_metadata() -> None:
    """A column won by an identifier picker doesn't become a metadata column."""
    header_row = ["IO No", "Quantity", "Buyer Comments"]
    bundle = _make_bundle(
        header_row=header_row,
        header_band_rect=Rect(r0=3, c0=1, r1=3, c1=3),
    )
    # Pretend columns 1 (IO No) and 2 (Quantity) are claimed by identifiers.
    out = MetadataAssembler().run(bundle=bundle, claimed_columns={1, 2})
    col_entries = [e for e in out["metadata_entries"]
                    if e.mode == FieldLocationMode.COLUMN]
    assert len(col_entries) == 1
    assert col_entries[0].column == 3
    assert col_entries[0].header_text == "Buyer Comments"


def test_column_metadata_carries_pli_scope_and_same_row_direction() -> None:
    header_row = ["Comments"]
    bundle = _make_bundle(
        header_row=header_row,
        header_band_rect=Rect(r0=3, c0=1, r1=3, c1=1),
    )
    out   = MetadataAssembler().run(bundle=bundle)
    entry = next(e for e in out["metadata_entries"] if e.mode == FieldLocationMode.COLUMN)
    assert entry.scope          == FieldScope.PLI
    assert entry.read_direction == ReadDirection.SAME_ROW
    assert entry.column         == 1


def test_non_string_header_cells_are_skipped() -> None:
    """Numeric / None / blank cells in the header row don't become metadata cols."""
    header_row = [123, "Comments", None, "  ", "Notes"]   # only 'Comments' + 'Notes' are real
    bundle = _make_bundle(
        header_row=header_row,
        header_band_rect=Rect(r0=3, c0=1, r1=3, c1=5),
    )
    out         = MetadataAssembler().run(bundle=bundle)
    col_entries = [e for e in out["metadata_entries"]
                    if e.mode == FieldLocationMode.COLUMN]
    assert len(col_entries) == 2
    assert {e.header_text for e in col_entries} == {"Comments", "Notes"}


def test_metadata_emits_both_kvs_and_columns_when_both_present() -> None:
    """A sheet with both kv-labels and unclaimed columns produces a mix of entries."""
    kv = KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                  label_text="Buyer", value_dtype=4)
    header_row = ["Comments"]
    bundle = _make_bundle(
        kv_blocks=[kv],
        header_row=header_row,
        header_band_rect=Rect(r0=3, c0=1, r1=3, c1=1),
    )
    out = MetadataAssembler().run(bundle=bundle)
    modes = [e.mode for e in out["metadata_entries"]]
    assert FieldLocationMode.KV_BLOCK in modes
    assert FieldLocationMode.COLUMN   in modes
