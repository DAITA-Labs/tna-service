"""QuantityExtractor — numeric coercion + Haystack wiring."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import DataRowRange, HeaderBand, Rect, StructureBag
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.field.quantity import QuantityExtractor


def _bundle_with(values, *, axis="vertical", columns=None, rows=None):
    n_rows = len(values)
    n_cols = len(values[0]) if values else 0
    canvas = GridCanvas(n_rows=n_rows, n_cols=n_cols, cell_values=values)
    bag = StructureBag()
    bag.header_band = HeaderBand(rect=Rect(2, 1, 2, n_cols), score=0.9)
    bag.data_row_ranges = [DataRowRange(row_start=3, row_end=n_rows)]
    hint = LayoutHint(
        axes=LayoutAxes(pli_axis=axis, stage_axis="none", subfield_axis="implicit"),
        cluster_id="c0", confidence=0.9,
        header_band=bag.header_band,
        data_row_ranges=bag.data_row_ranges,
        candidate_columns=columns if columns is not None else {"quantity": [1]},
        candidate_rows=rows if rows is not None else {"quantity": list(range(3, n_rows + 1))},
    )
    return ClusterAnchorBundle(
        cluster=PliCluster(cluster_id="c0", sheet_names=["S"], role="pli_cluster"),
        anchor_sheet_name="S", canvas=canvas, bag=bag, hint=hint,
    )


def test_int_quantities_kept_as_int() -> None:
    bundle = _bundle_with([[None], ["Qty"], [1200], [500]])
    out = QuantityExtractor().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [1200, 500]


def test_integer_valued_floats_coerced_to_int() -> None:
    """openpyxl often types int cells as float — we collapse back."""
    bundle = _bundle_with([[None], ["Qty"], [1200.0], [500.0]])
    out = QuantityExtractor().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [1200, 500]


def test_genuinely_fractional_floats_preserved() -> None:
    bundle = _bundle_with([[None], ["Qty"], [1200.5]])
    out = QuantityExtractor().run(bundle=bundle)
    assert out["findings"][0].value == 1200.5


def test_string_quantities_with_thousands_separator() -> None:
    bundle = _bundle_with([[None], ["Qty"], ["1,200"], ["500"], ["3 000"]])
    out = QuantityExtractor().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [1200, 500, 3000]


def test_string_quantities_with_unit_suffix() -> None:
    bundle = _bundle_with([[None], ["Qty"], ["1200 pcs"], ["500 units"], ["50 ea"]])
    out = QuantityExtractor().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [1200, 500, 50]


def test_unparseable_string_kept_as_raw() -> None:
    """Garbage strings preserved so validators can flag them downstream."""
    bundle = _bundle_with([[None], ["Qty"], ["TBD"]])
    out = QuantityExtractor().run(bundle=bundle)
    assert out["findings"][0].value == "TBD"


def test_blank_and_zero_skipped() -> None:
    """Blank cells and zero values aren't emitted — they don't represent orders."""
    bundle = _bundle_with([
        [None], ["Qty"],
        [None], [""], [0], [0.0], ["0"],
        [100],
    ])
    out = QuantityExtractor().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [100]


def test_bool_rejected() -> None:
    """Bool is a subclass of int — defensively skipped."""
    bundle = _bundle_with([[None], ["Qty"], [True]])
    out = QuantityExtractor().run(bundle=bundle)
    assert out["findings"] == []


def test_each_finding_carries_quantity_canonical_and_coords() -> None:
    bundle = _bundle_with([[None], ["Qty"], [100]])
    out = QuantityExtractor().run(bundle=bundle)
    f = out["findings"][0]
    assert f.canonical == "quantity"
    assert f.value_coord == ("A", 3)
    assert f.label_coord == ("A", 2)


def test_no_candidate_columns_yields_no_findings() -> None:
    bundle = _bundle_with([[None], ["Qty"], [100]], columns={})
    assert QuantityExtractor().run(bundle=bundle)["findings"] == []


def test_unsupported_pli_axis_returns_empty_list() -> None:
    for axis in ("sectional", "sheet", "horizontal"):
        bundle = _bundle_with([[None], ["Qty"], [100]], axis=axis)
        assert QuantityExtractor().run(bundle=bundle)["findings"] == []


def test_extractor_sockets_registered() -> None:
    comp = QuantityExtractor()
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "findings" in comp.__haystack_output__._sockets_dict


def test_extractor_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("quantity", QuantityExtractor())
    assert "quantity" in pipeline.graph.nodes
