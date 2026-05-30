"""StageStructureValidator — structural invariants of detected StageBands.

One section per `_check_*` helper. Each section's tests construct the
minimal bag state required to exercise that invariant in isolation.
"""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.structure import (
    MergeSpan,
    Rect,
    StageBand,
    SubfieldCluster,
)
from app.components.validators.stage_structure import StageStructureValidator
from tests.fixtures.bundles import make_bundle


def _band(name: str, *, r0: int, c0: int, c1: int,
          name_col: str | None = None, name_row: int | None = None) -> StageBand:
    """Build a StageBand whose arena spans (r0..r0, c0..c1) and name sits at name_row.

    Defaults: name_coord is anchored at column = c0's letter and row = r0 - 1
    (the typical sub-header row).
    """
    from openpyxl.utils import get_column_letter
    return StageBand(
        rect=Rect(r0=r0, c0=c0, r1=r0 + 2, c1=c1),
        name_coord=(name_col or get_column_letter(c0), name_row if name_row is not None else r0 - 1),
        name_text=name,
    )


def _cluster(parent_band_id: int, row: int, cols: list[int]) -> SubfieldCluster:
    return SubfieldCluster(
        parent_band_id=parent_band_id,
        subfield_coords=tuple((row, c) for c in cols),
    )


def _grid(n_rows: int, n_cols: int) -> list[list[object]]:
    return [[None] * n_cols for _ in range(n_rows)]


def _bundle_with(stage_bands=None, subfield_clusters=None, merge_spans=None,
                 values=None, n_rows: int = 8, n_cols: int = 12):
    """Build a minimal bundle wrapping the supplied structure records."""
    values = values if values is not None else _grid(n_rows, n_cols)
    return make_bundle(
        values, "io_number", columns={}, rows={},
        stage_bands=stage_bands,
        subfield_clusters=subfield_clusters,
        merge_spans=merge_spans,
    )


# ─── Happy path ─────────────────────────────────────────────────────────


def test_well_formed_bands_yield_no_warnings() -> None:
    """Three bands sharing arena row, sub-header row, merge backing, and shape."""
    bands = [
        _band("Fabric",  r0=4, c0=2, c1=4),
        _band("Cutting", r0=4, c0=5, c1=7),
        _band("Sewing",  r0=4, c0=8, c1=10),
    ]
    values = _grid(8, 12)
    # Place recognised sub-headers under each band at row 3 (= 4 - 1).
    for c in (2, 5, 8):
        values[2][c - 1] = "Plan"
    for c in (3, 6, 9):
        values[2][c - 1] = "Actual"
    for c in (4, 7, 10):
        values[2][c - 1] = "Status"
    clusters = [
        _cluster(0, row=3, cols=[2, 3, 4]),
        _cluster(1, row=3, cols=[5, 6, 7]),
        _cluster(2, row=3, cols=[8, 9, 10]),
    ]
    merges = [
        MergeSpan(rect=Rect(3, 2, 3, 4), orientation="horizontal"),
        MergeSpan(rect=Rect(3, 5, 3, 7), orientation="horizontal"),
        MergeSpan(rect=Rect(3, 8, 3, 10), orientation="horizontal"),
    ]
    bundle = _bundle_with(stage_bands=bands, subfield_clusters=clusters,
                          merge_spans=merges, values=values)
    assert StageStructureValidator().run(bundle=bundle)["warnings"] == []


# ─── _check_anchor_row_alignment ────────────────────────────────────────


def test_anchor_row_mismatch_emits_error_for_outlier() -> None:
    bands = [
        _band("Fabric",  r0=4, c0=2, c1=4),
        _band("Cutting", r0=4, c0=5, c1=7),
        _band("Sewing",  r0=5, c0=8, c1=10),    # outlier
    ]
    warnings = StageStructureValidator().run(bundle=_bundle_with(stage_bands=bands))["warnings"]
    misaligned = [w for w in warnings if w.name == "stage_band_anchor_row_misaligned"]
    assert len(misaligned) == 1
    assert misaligned[0].severity == "error"
    assert "Sewing" in misaligned[0].message
    assert "row 5" in misaligned[0].message


def test_single_band_skips_anchor_check() -> None:
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]
    warnings = StageStructureValidator().run(bundle=_bundle_with(stage_bands=bands))["warnings"]
    assert [w for w in warnings if w.name == "stage_band_anchor_row_misaligned"] == []


# ─── _check_subheader_row_alignment ─────────────────────────────────────


def test_subheader_row_split_emits_error() -> None:
    """Sub-headers spanning two rows under one band."""
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]
    clusters = [SubfieldCluster(parent_band_id=0,
                                subfield_coords=((3, 2), (2, 3)))]   # rows 2 + 3
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, subfield_clusters=clusters),
    )["warnings"]
    split = [w for w in warnings if w.name == "subheader_row_split"]
    assert len(split) == 1
    assert split[0].severity == "error"


def test_subheader_row_offset_from_parent_emits_error() -> None:
    """Sub-headers at row != band.rect.r0 - 1."""
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]    # expects sub-headers at row 3
    clusters = [_cluster(0, row=2, cols=[2, 3, 4])]
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, subfield_clusters=clusters),
    )["warnings"]
    offset = [w for w in warnings if w.name == "subheader_row_offset"]
    assert len(offset) == 1
    assert "row 2" in offset[0].message
    assert "row 3" in offset[0].message


def test_subheader_aligned_no_warning() -> None:
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]
    clusters = [_cluster(0, row=3, cols=[2, 3, 4])]
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, subfield_clusters=clusters),
    )["warnings"]
    assert [w for w in warnings if w.name.startswith("subheader_row")] == []


# ─── _check_column_range_matches_merge ──────────────────────────────────


def test_band_with_no_matching_merge_emits_warning() -> None:
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]
    # No merge spans at all → fallback-anchored.
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, merge_spans=[]),
    )["warnings"]
    fallback = [w for w in warnings if w.name == "stage_band_no_merge_anchor"]
    assert len(fallback) == 1
    assert fallback[0].severity == "warning"
    assert "Fabric" in fallback[0].message


def test_band_with_partial_merge_emits_warning() -> None:
    """Merge exists but doesn't span the full band column range."""
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]
    merges = [MergeSpan(rect=Rect(3, 2, 3, 3), orientation="horizontal")]   # c0..c1 = 2..3, not 2..4
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, merge_spans=merges),
    )["warnings"]
    fallback = [w for w in warnings if w.name == "stage_band_no_merge_anchor"]
    assert len(fallback) == 1


def test_vertical_merge_does_not_satisfy_check() -> None:
    """Only horizontal merges count as super-header backing."""
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]
    merges = [MergeSpan(rect=Rect(3, 2, 3, 4), orientation="vertical")]
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, merge_spans=merges),
    )["warnings"]
    assert [w for w in warnings if w.name == "stage_band_no_merge_anchor"]


# ─── _check_sub_field_count_consistency ─────────────────────────────────


def test_subfield_count_outlier_emits_warning() -> None:
    bands = [
        _band("Fabric",  r0=4, c0=2, c1=4),
        _band("Cutting", r0=4, c0=5, c1=7),
        _band("Sewing",  r0=4, c0=8, c1=10),
    ]
    clusters = [
        _cluster(0, row=3, cols=[2, 3, 4]),     # 3 sub-cols
        _cluster(1, row=3, cols=[5, 6, 7]),     # 3
        _cluster(2, row=3, cols=[8, 9]),        # 2 — outlier
    ]
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, subfield_clusters=clusters),
    )["warnings"]
    outliers = [w for w in warnings if w.name == "stage_band_subfield_count_outlier"]
    assert len(outliers) == 1
    assert outliers[0].severity == "warning"
    assert "Sewing" in outliers[0].message


def test_consistent_subfield_counts_no_warning() -> None:
    bands = [
        _band("Fabric",  r0=4, c0=2, c1=4),
        _band("Cutting", r0=4, c0=5, c1=7),
    ]
    clusters = [
        _cluster(0, row=3, cols=[2, 3, 4]),
        _cluster(1, row=3, cols=[5, 6, 7]),
    ]
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, subfield_clusters=clusters),
    )["warnings"]
    assert [w for w in warnings if w.name == "stage_band_subfield_count_outlier"] == []


def test_single_cluster_skips_count_check() -> None:
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]
    clusters = [_cluster(0, row=3, cols=[2, 3, 4])]
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, subfield_clusters=clusters),
    )["warnings"]
    assert [w for w in warnings if w.name == "stage_band_subfield_count_outlier"] == []


# ─── _check_sub_header_text_recognised ──────────────────────────────────


def test_unrecognised_subheaders_emit_info() -> None:
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]
    clusters = [_cluster(0, row=3, cols=[2, 3, 4])]
    values = _grid(8, 12)
    values[2][1] = "Foo"
    values[2][2] = "Bar"
    values[2][3] = "Baz"
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, subfield_clusters=clusters, values=values),
    )["warnings"]
    info = [w for w in warnings if w.name == "stage_band_unrecognised_subheaders"]
    assert len(info) == 1
    assert info[0].severity == "info"
    assert "Fabric" in info[0].message


def test_at_least_one_recognised_subheader_silences_check() -> None:
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]
    clusters = [_cluster(0, row=3, cols=[2, 3, 4])]
    values = _grid(8, 12)
    values[2][1] = "Plan"          # recognised
    values[2][2] = "MysteryLabel"
    values[2][3] = "Foo"
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, subfield_clusters=clusters, values=values),
    )["warnings"]
    assert [w for w in warnings if w.name == "stage_band_unrecognised_subheaders"] == []


def test_empty_subheader_cells_skip_recognition_check() -> None:
    """A cluster with no string sub-headers (blank cells) doesn't emit info."""
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]
    clusters = [_cluster(0, row=3, cols=[2, 3, 4])]
    warnings = StageStructureValidator().run(
        bundle=_bundle_with(stage_bands=bands, subfield_clusters=clusters),
    )["warnings"]
    assert [w for w in warnings if w.name == "stage_band_unrecognised_subheaders"] == []


# ─── Degenerate inputs ────────────────────────────────────────────────────


def test_no_stage_bands_yields_no_warnings() -> None:
    assert StageStructureValidator().run(bundle=_bundle_with())["warnings"] == []


def test_dangling_cluster_parent_id_skipped() -> None:
    """A SubfieldCluster pointing past the band list is ignored, not crashing."""
    bands = [_band("Fabric", r0=4, c0=2, c1=4)]
    clusters = [_cluster(0, row=3, cols=[2, 3]),
                _cluster(99, row=3, cols=[5, 6])]
    bundle = _bundle_with(stage_bands=bands, subfield_clusters=clusters)
    StageStructureValidator().run(bundle=bundle)


# ─── Component plumbing ──────────────────────────────────────────────────


def test_validator_sockets_registered() -> None:
    comp = StageStructureValidator()
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "warnings" in comp.__haystack_output__._sockets_dict


def test_validator_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("stage_struct", StageStructureValidator())
    assert "stage_struct" in pipeline.graph.nodes
