"""Workbook artifacts — SheetSignature + PliCluster shape and defaults."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import StructureBag
from app.artifacts.workbook import (
    SIGNATURE_LABEL_ROWS,
    SIGNATURE_SAMPLE_ROWS,
    ClusterAnchorBundle,
    PliCluster,
    SheetSignature,
)


def test_sheet_signature_defaults_to_empty_collections() -> None:
    """A signature with only required fields carries empty mask / dtype / labels."""
    sig = SheetSignature(sheet_name="S1", n_rows=10, n_cols=5)
    assert sig.non_blank_mask == frozenset()
    assert sig.dtype_per_row == ()
    assert sig.label_positions == frozenset()


def test_sheet_signature_is_frozen() -> None:
    """SheetSignature is frozen — mutation raises FrozenInstanceError."""
    import dataclasses
    sig = SheetSignature(sheet_name="S1", n_rows=10, n_cols=5)
    try:
        sig.sheet_name = "S2"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("SheetSignature must be frozen")


def test_pli_cluster_defaults_to_unknown_role() -> None:
    """A new cluster starts as 'unknown' until the role classifier runs."""
    cluster = PliCluster(cluster_id="c0")
    assert cluster.role == "unknown"
    assert cluster.sheet_names == []


def test_pli_cluster_accepts_role_label() -> None:
    """The clusterer / role classifier can write to the role field."""
    cluster = PliCluster(cluster_id="c0", sheet_names=["S1", "S2"])
    cluster.role = "pli_cluster"
    assert cluster.role == "pli_cluster"


def test_signature_sample_row_constants_are_sensible() -> None:
    """SAMPLE_ROWS covers header + first data rows; LABEL_ROWS covers headers only."""
    assert SIGNATURE_SAMPLE_ROWS >= 10
    assert 1 <= SIGNATURE_LABEL_ROWS <= SIGNATURE_SAMPLE_ROWS


def test_cluster_anchor_bundle_carries_phase_artifacts() -> None:
    """ClusterAnchorBundle is frozen and bundles cluster + canvas + bag + hint."""
    cluster = PliCluster(cluster_id="c0", sheet_names=["S"], role="pli_cluster")
    canvas = GridCanvas(n_rows=1, n_cols=1, cell_values=[[None]])
    bag = StructureBag()
    hint = LayoutHint(
        axes=LayoutAxes(pli_axis="vertical", stage_axis="none", subfield_axis="implicit"),
        cluster_id="c0", confidence=0.5,
    )
    bundle = ClusterAnchorBundle(
        cluster=cluster, anchor_sheet_name="S",
        canvas=canvas, bag=bag, hint=hint,
    )
    assert bundle.cluster is cluster
    assert bundle.anchor_sheet_name == "S"
    assert bundle.hint.cluster_id == "c0"
