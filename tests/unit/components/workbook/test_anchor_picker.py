"""Anchor picker — choose the structure-phase anchor sheet per cluster."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.workbook import PliCluster, SheetSignature
from app.components.workbook.anchor_picker import (
    AnchorPicker,
    pick_anchor_sheet_name,
)


def _sig(name: str, n_cells: int) -> SheetSignature:
    """Build a signature with `n_cells` populated coordinates."""
    cells = frozenset((1, c) for c in range(1, n_cells + 1))
    return SheetSignature(sheet_name=name, n_rows=1, n_cols=n_cells, non_blank_mask=cells)


def test_pick_anchor_for_empty_cluster_returns_none() -> None:
    cluster = PliCluster(cluster_id="c0")
    assert pick_anchor_sheet_name(cluster, []) is None


def test_pick_anchor_for_singleton_cluster_picks_only_sheet() -> None:
    cluster = PliCluster(cluster_id="c0", sheet_names=["Only"])
    sigs = [_sig("Only", 5)]
    assert pick_anchor_sheet_name(cluster, sigs) == "Only"


def test_pick_anchor_chooses_richest_signature() -> None:
    """Among 3 cluster sheets, the one with the largest non_blank_mask wins."""
    cluster = PliCluster(cluster_id="c0", sheet_names=["A", "B", "C"])
    sigs = [_sig("A", 10), _sig("B", 30), _sig("C", 15)]
    assert pick_anchor_sheet_name(cluster, sigs) == "B"


def test_pick_anchor_ties_broken_by_cluster_order() -> None:
    """Equal-rich signatures → earlier sheet name in cluster wins."""
    cluster = PliCluster(cluster_id="c0", sheet_names=["First", "Second"])
    sigs = [_sig("First", 10), _sig("Second", 10)]
    assert pick_anchor_sheet_name(cluster, sigs) == "First"


def test_pick_anchor_returns_none_when_no_signatures_match_cluster_sheets() -> None:
    """If signatures are present but none match the cluster sheet names, return None."""
    cluster = PliCluster(cluster_id="c0", sheet_names=["Ghost"])
    sigs = [_sig("OtherSheet", 5)]
    assert pick_anchor_sheet_name(cluster, sigs) is None


def test_anchor_picker_component_returns_anchor_sheet_name() -> None:
    cluster = PliCluster(cluster_id="c0", sheet_names=["A", "B"])
    sigs = [_sig("A", 4), _sig("B", 20)]
    out = AnchorPicker().run(cluster=cluster, signatures=sigs)
    assert out == {"anchor_sheet_name": "B"}


def test_anchor_picker_component_sockets_registered() -> None:
    comp = AnchorPicker()
    assert {"cluster", "signatures"}.issubset(comp.__haystack_input__._sockets_dict.keys())
    assert "anchor_sheet_name" in comp.__haystack_output__._sockets_dict


def test_anchor_picker_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("anchor", AnchorPicker())
    assert "anchor" in pipeline.graph.nodes
