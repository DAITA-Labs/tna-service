"""RoleClassifier + sheet selector — classify clusters and filter to PLI-only."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import (
    DateStrip,
    FloatStrip,
    HeaderBand,
    IntStrip,
    KvBlock,
    Rect,
    StructureBag,
)
from app.artifacts.workbook import PliCluster
from app.components.workbook.role_classifier import (
    classify_cluster_role,
    filter_pli_clusters,
)


def _blank_canvas(n_rows: int = 5, n_cols: int = 5) -> GridCanvas:
    return GridCanvas(
        n_rows=n_rows, n_cols=n_cols,
        cell_values=[[None] * n_cols for _ in range(n_rows)],
    )


def _bag_with(date: bool = False, ints: bool = False, floats: bool = False,
                kv: bool = False, header_band: bool = False) -> StructureBag:
    bag = StructureBag()
    if date:
        bag.date_strips = [DateStrip(rect=Rect(1, 1, 5, 1), orientation="vertical", density=1.0)]
    if ints:
        bag.int_strips = [IntStrip(rect=Rect(1, 2, 5, 2), magnitude="medium",
                                     density=1.0)]
    if floats:
        bag.float_strips = [FloatStrip(rect=Rect(1, 3, 5, 3), density=1.0)]
    if kv:
        bag.kv_blocks = [KvBlock(label_coord=("A", 1), value_coord=("B", 1),
                                   label_text="Job", value_dtype=2)]
    if header_band:
        bag.header_band = HeaderBand(rect=Rect(1, 1, 1, 4), score=0.9)
    return bag


def test_no_dates_classifies_as_other_sheets() -> None:
    cluster = PliCluster(cluster_id="c0", sheet_names=["S"])
    role = classify_cluster_role(cluster, _blank_canvas(), _bag_with(ints=True, kv=True))
    assert role == "other_sheets"
    assert cluster.role == "other_sheets"


def test_no_numeric_value_cells_classifies_as_other_sheets() -> None:
    cluster = PliCluster(cluster_id="c0", sheet_names=["S"])
    role = classify_cluster_role(cluster, _blank_canvas(), _bag_with(date=True, kv=True))
    assert role == "other_sheets"


def test_dates_plus_numbers_plus_kv_classifies_as_pli_cluster() -> None:
    cluster = PliCluster(cluster_id="c0", sheet_names=["S"])
    role = classify_cluster_role(cluster, _blank_canvas(),
                                   _bag_with(date=True, ints=True, kv=True))
    assert role == "pli_cluster"


def test_dates_plus_floats_plus_kv_classifies_as_pli_cluster() -> None:
    """IntStrip OR FloatStrip satisfies the numeric requirement."""
    cluster = PliCluster(cluster_id="c0", sheet_names=["S"])
    role = classify_cluster_role(cluster, _blank_canvas(),
                                   _bag_with(date=True, floats=True, kv=True))
    assert role == "pli_cluster"


def test_dates_plus_numbers_plus_id_alias_in_header_classifies_as_pli_cluster() -> None:
    """No kv_blocks but a header band whose row contains an identifier alias passes."""
    canvas = GridCanvas(
        n_rows=2, n_cols=4,
        cell_values=[["IO No", "Style", "Qty", "Delivery"],
                       [None, None, None, None]],
    )
    bag = _bag_with(date=True, ints=True, header_band=True)
    cluster = PliCluster(cluster_id="c0", sheet_names=["S"])
    role = classify_cluster_role(cluster, canvas, bag)
    assert role == "pli_cluster"


def test_dates_plus_numbers_but_no_kv_and_no_alias_classifies_as_other_sheets() -> None:
    """Header band whose row text matches no identifier alias fails the third signal."""
    canvas = GridCanvas(
        n_rows=2, n_cols=4,
        cell_values=[["Buyer", "Season", "Brand", "Year"],
                       [None, None, None, None]],
    )
    bag = _bag_with(date=True, ints=True, header_band=True)
    cluster = PliCluster(cluster_id="c0", sheet_names=["S"])
    role = classify_cluster_role(cluster, canvas, bag)
    assert role == "other_sheets"


def test_filter_pli_clusters_drops_other_sheets() -> None:
    pli_one = PliCluster(cluster_id="c0", sheet_names=["A"], role="pli_cluster")
    other = PliCluster(cluster_id="c1", sheet_names=["B"], role="other_sheets")
    pli_two = PliCluster(cluster_id="c2", sheet_names=["C"], role="pli_cluster")
    unknown = PliCluster(cluster_id="c3", sheet_names=["D"], role="unknown")
    kept = filter_pli_clusters([pli_one, other, pli_two, unknown])
    assert [c.cluster_id for c in kept] == ["c0", "c2"]
