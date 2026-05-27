"""IoNumberExtractor — io_number extraction + Haystack wiring."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import DataRowRange, HeaderBand, Rect, StructureBag
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.field.io_number import IoNumberExtractor


def _bundle_with(values, *, axis="vertical", columns=None, rows=None):
    """Build a bundle whose anchor canvas carries `values`."""
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
        candidate_columns=columns if columns is not None else {"io_number": [1]},
        candidate_rows=rows if rows is not None else {"io_number": list(range(3, n_rows + 1))},
    )
    return ClusterAnchorBundle(
        cluster=PliCluster(cluster_id="c0", sheet_names=["S"], role="pli_cluster"),
        anchor_sheet_name="S", canvas=canvas, bag=bag, hint=hint,
    )


def test_string_io_codes_kept_as_strings_with_whitespace_stripped() -> None:
    bundle = _bundle_with([
        [None] * 1,
        ["IO No"],
        [" IO-3 "],
        ["IO-4"],
    ])
    out = IoNumberExtractor().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == ["IO-3", "IO-4"]


def test_int_io_codes_coerced_to_str() -> None:
    bundle = _bundle_with([
        [None],
        ["IO No"],
        [1063],
        [1064],
    ])
    out = IoNumberExtractor().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == ["1063", "1064"]


def test_float_io_codes_drop_trailing_zero() -> None:
    """openpyxl sometimes types integer-valued cells as float — coerce back."""
    bundle = _bundle_with([
        [None],
        ["IO No"],
        [1063.0],
        [1064.5],   # non-integer float kept as-is
    ])
    out = IoNumberExtractor().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == ["1063", "1064.5"]


def test_blank_cells_skipped() -> None:
    bundle = _bundle_with([
        [None],
        ["IO No"],
        ["IO-3"],
        [None],
        [""],
        ["IO-6"],
    ])
    out = IoNumberExtractor().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == ["IO-3", "IO-6"]


def test_each_finding_carries_io_number_canonical_and_coords() -> None:
    bundle = _bundle_with([[None], ["IO No"], ["X-1"]])
    out = IoNumberExtractor().run(bundle=bundle)
    f = out["findings"][0]
    assert f.canonical == "io_number"
    assert f.value_coord == ("A", 3)
    assert f.label_coord == ("A", 2)
    assert "HEADER_BAND_MEMBER" in f.evidence


def test_no_candidate_columns_yields_no_findings() -> None:
    bundle = _bundle_with([[None], ["IO No"], ["X-1"]], columns={})
    assert IoNumberExtractor().run(bundle=bundle)["findings"] == []


def test_no_candidate_rows_yields_no_findings() -> None:
    bundle = _bundle_with([[None], ["IO No"], ["X-1"]], rows={})
    assert IoNumberExtractor().run(bundle=bundle)["findings"] == []


def test_unsupported_pli_axis_returns_empty_list() -> None:
    """Sectional / sheet / horizontal axes return [] until extractors implement them."""
    for axis in ("sectional", "sheet", "horizontal"):
        bundle = _bundle_with([[None], ["IO No"], ["X-1"]], axis=axis)
        assert IoNumberExtractor().run(bundle=bundle)["findings"] == []


def test_extractor_sockets_registered() -> None:
    comp = IoNumberExtractor()
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "findings" in comp.__haystack_output__._sockets_dict


def test_extractor_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("io_number", IoNumberExtractor())
    assert "io_number" in pipeline.graph.nodes
