"""Clusterer — union-find grouping of sheets by signature similarity."""
from __future__ import annotations

import openpyxl

from app.components.workbook.clusterer import DEFAULT_THRESHOLD, cluster_sheets
from app.components.workbook.profiler import compute_sheet_signature


def _ws(title: str, cells):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title
    for r, c, v in cells:
        ws.cell(row=r, column=c, value=v)
    return ws


_TEMPLATE_A = [
    (1, 1, "IO No"), (1, 2, "Style"), (1, 3, "Qty"), (1, 4, "Delivery"),
    (2, 1, "IO-1"), (2, 2, "S001"), (2, 3, 100), (2, 4, "2026-05-01"),
]

_TEMPLATE_B = [
    (1, 1, "Buyer"), (1, 2, "Season"), (1, 3, "Brand"),
    (2, 1, "Acme"), (2, 2, "FW26"), (2, 3, "BX"),
]


def test_empty_input_yields_empty_clusters() -> None:
    assert cluster_sheets([]) == []


def test_single_signature_makes_one_cluster() -> None:
    sig = compute_sheet_signature(_ws("S", _TEMPLATE_A))
    clusters = cluster_sheets([sig])
    assert len(clusters) == 1
    assert clusters[0].cluster_id == "c0"
    assert clusters[0].sheet_names == ["S"]


def test_two_similar_sheets_merge_into_one_cluster() -> None:
    a = compute_sheet_signature(_ws("Sheet1", _TEMPLATE_A))
    b = compute_sheet_signature(_ws("Sheet2", _TEMPLATE_A))
    clusters = cluster_sheets([a, b])
    assert len(clusters) == 1
    assert set(clusters[0].sheet_names) == {"Sheet1", "Sheet2"}


def test_dissimilar_sheets_stay_separate() -> None:
    a = compute_sheet_signature(_ws("PliSheet", _TEMPLATE_A))
    b = compute_sheet_signature(_ws("InfoSheet", _TEMPLATE_B))
    clusters = cluster_sheets([a, b])
    assert len(clusters) == 2
    ids = {c.cluster_id for c in clusters}
    assert ids == {"c0", "c1"}


def test_cluster_ids_assigned_in_discovery_order() -> None:
    """First sheet's cluster is c0; the first sheet of a new template is c1."""
    a = compute_sheet_signature(_ws("A", _TEMPLATE_A))
    b = compute_sheet_signature(_ws("B", _TEMPLATE_B))
    c = compute_sheet_signature(_ws("C", _TEMPLATE_A))
    clusters = cluster_sheets([a, b, c])
    # Three signatures → two clusters: {A, C} = c0; {B} = c1
    by_id = {c.cluster_id: c for c in clusters}
    assert set(by_id["c0"].sheet_names) == {"A", "C"}
    assert by_id["c1"].sheet_names == ["B"]


def test_threshold_can_be_overridden() -> None:
    """Lower threshold allows weaker matches to merge."""
    a = compute_sheet_signature(_ws("A", _TEMPLATE_A))
    b = compute_sheet_signature(_ws("B", _TEMPLATE_B))
    # At default threshold they stay split
    assert len(cluster_sheets([a, b])) == 2
    # At threshold 0 they all collapse to one
    assert len(cluster_sheets([a, b], threshold=0.0)) == 1


def test_default_threshold_constant_value() -> None:
    assert DEFAULT_THRESHOLD == 0.8


def test_three_clones_one_outlier_yields_two_clusters() -> None:
    """3 sheets of template A + 1 of template B → 2 clusters of sizes 3 and 1."""
    sigs = [
        compute_sheet_signature(_ws(f"P{i}", _TEMPLATE_A))
        for i in range(3)
    ]
    sigs.append(compute_sheet_signature(_ws("Other", _TEMPLATE_B)))
    clusters = cluster_sheets(sigs)
    assert len(clusters) == 2
    sizes = sorted(len(c.sheet_names) for c in clusters)
    assert sizes == [1, 3]
