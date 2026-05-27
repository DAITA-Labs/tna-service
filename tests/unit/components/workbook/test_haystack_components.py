"""Haystack @component wrappers: WorkbookProfiler / SheetClusterer / ClusterRoleClassifier / PliClusterFilter."""
from __future__ import annotations

import openpyxl
from haystack import Pipeline

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import (
    DateStrip,
    HeaderBand,
    IntStrip,
    KvBlock,
    Rect,
    StructureBag,
)
from app.artifacts.workbook import PliCluster, SheetSignature
from app.components.workbook.clusterer import SheetClusterer
from app.components.workbook.profiler import WorkbookProfiler
from app.components.workbook.role_classifier import (
    ClusterRoleClassifier,
    PliClusterFilter,
)


def _wb_with_sheets(*sheet_specs):
    """Build an openpyxl workbook with one sheet per (title, cells) pair."""
    wb = openpyxl.Workbook()
    default = wb.active
    if sheet_specs:
        default.title = sheet_specs[0][0]
        for r, c, v in sheet_specs[0][1]:
            default.cell(row=r, column=c, value=v)
    for title, cells in sheet_specs[1:]:
        ws = wb.create_sheet(title=title)
        for r, c, v in cells:
            ws.cell(row=r, column=c, value=v)
    return wb


# ─── WorkbookProfiler ───────────────────────────────────────────────────────


def test_workbook_profiler_emits_one_signature_per_sheet() -> None:
    wb = _wb_with_sheets(
        ("PLI-A", [(1, 1, "IO No"), (2, 1, "IO-1")]),
        ("PLI-B", [(1, 1, "Style"), (2, 1, "S001")]),
    )
    out = WorkbookProfiler().run(workbook=wb)
    assert set(out.keys()) == {"signatures"}
    assert len(out["signatures"]) == 2
    assert {s.sheet_name for s in out["signatures"]} == {"PLI-A", "PLI-B"}


def test_workbook_profiler_socket_metadata_registered() -> None:
    comp = WorkbookProfiler()
    assert "workbook" in comp.__haystack_input__._sockets_dict
    assert "signatures" in comp.__haystack_output__._sockets_dict


# ─── SheetClusterer ─────────────────────────────────────────────────────────


def _signature(name: str, mask_cells=((1, 1),)) -> SheetSignature:
    return SheetSignature(
        sheet_name=name, n_rows=2, n_cols=2,
        non_blank_mask=frozenset(mask_cells),
    )


def test_sheet_clusterer_returns_clusters() -> None:
    sigs = [_signature("A"), _signature("B")]
    out = SheetClusterer().run(signatures=sigs)
    assert set(out.keys()) == {"clusters"}
    assert all(isinstance(c, PliCluster) for c in out["clusters"])


def test_sheet_clusterer_threshold_override_constructor_arg() -> None:
    """A SheetClusterer constructed with a low threshold merges aggressively."""
    sigs = [_signature("A"), _signature("B", mask_cells=((2, 2),))]
    strict = SheetClusterer().run(signatures=sigs)["clusters"]
    lenient = SheetClusterer(threshold=0.0).run(signatures=sigs)["clusters"]
    assert len(strict) == 2
    assert len(lenient) == 1


def test_sheet_clusterer_pipeline_addable() -> None:
    pipeline = Pipeline()
    pipeline.add_component("clusterer", SheetClusterer())
    assert "clusterer" in pipeline.graph.nodes


# ─── ClusterRoleClassifier ──────────────────────────────────────────────────


def _bag_with_pli_signals() -> StructureBag:
    bag = StructureBag()
    bag.date_strips = [DateStrip(rect=Rect(1, 1, 5, 1), orientation="vertical", density=1.0)]
    bag.int_strips = [IntStrip(rect=Rect(1, 2, 5, 2), magnitude="medium", density=1.0)]
    bag.kv_blocks = [KvBlock(label_coord=("A", 1), value_coord=("B", 1),
                                label_text="Job", value_dtype=2)]
    return bag


def test_role_classifier_mutates_cluster_role() -> None:
    cluster = PliCluster(cluster_id="c0", sheet_names=["S"])
    canvas = GridCanvas(n_rows=5, n_cols=5, cell_values=[[None] * 5 for _ in range(5)])
    out = ClusterRoleClassifier().run(cluster=cluster, canvas=canvas, bag=_bag_with_pli_signals())
    assert out["role"] == "pli_cluster"
    assert out["cluster"].role == "pli_cluster"
    assert out["cluster"] is cluster


def test_role_classifier_other_sheets_when_signals_absent() -> None:
    cluster = PliCluster(cluster_id="c0", sheet_names=["S"])
    canvas = GridCanvas(n_rows=5, n_cols=5, cell_values=[[None] * 5 for _ in range(5)])
    out = ClusterRoleClassifier().run(cluster=cluster, canvas=canvas, bag=StructureBag())
    assert out["role"] == "other_sheets"


# ─── PliClusterFilter ───────────────────────────────────────────────────────


def test_pli_cluster_filter_keeps_only_pli_clusters() -> None:
    clusters = [
        PliCluster(cluster_id="c0", sheet_names=["A"], role="pli_cluster"),
        PliCluster(cluster_id="c1", sheet_names=["B"], role="other_sheets"),
        PliCluster(cluster_id="c2", sheet_names=["C"], role="unknown"),
    ]
    out = PliClusterFilter().run(clusters=clusters)
    assert [c.cluster_id for c in out["pli_clusters"]] == ["c0"]
