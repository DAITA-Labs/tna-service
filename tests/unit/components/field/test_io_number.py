"""IoNumberComponent + IoNumberExtractor — io_number extraction + Haystack wiring."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import DataRowRange, HeaderBand, Rect, StructureBag
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.field.io_number import IoNumberComponent, IoNumberExtractor


def _bundle_with(values):
    """Build a vertical-PLI bundle whose anchor canvas carries `values`."""
    n_rows = len(values)
    n_cols = len(values[0]) if values else 0
    canvas = GridCanvas(n_rows=n_rows, n_cols=n_cols, cell_values=values)
    bag = StructureBag()
    bag.header_band = HeaderBand(rect=Rect(2, 1, 2, n_cols), score=0.9)
    bag.data_row_ranges = [DataRowRange(row_start=3, row_end=n_rows)]
    hint = LayoutHint(
        axes=LayoutAxes(pli_axis="vertical", stage_axis="none", subfield_axis="implicit"),
        cluster_id="c0", confidence=0.9,
        header_band=bag.header_band,
        data_row_ranges=bag.data_row_ranges,
        candidate_columns={"io_number": [1]},
        candidate_rows={"io_number": list(range(3, n_rows + 1))},
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
    findings = IoNumberComponent().extract_findings(bundle)
    assert [f.value for f in findings] == ["IO-3", "IO-4"]


def test_int_io_codes_coerced_to_str() -> None:
    bundle = _bundle_with([
        [None],
        ["IO No"],
        [1063],
        [1064],
    ])
    findings = IoNumberComponent().extract_findings(bundle)
    assert [f.value for f in findings] == ["1063", "1064"]


def test_float_io_codes_drop_trailing_zero() -> None:
    """openpyxl sometimes types integer-valued cells as float — coerce back."""
    bundle = _bundle_with([
        [None],
        ["IO No"],
        [1063.0],
        [1064.5],   # non-integer float kept as-is
    ])
    findings = IoNumberComponent().extract_findings(bundle)
    assert [f.value for f in findings] == ["1063", "1064.5"]


def test_blank_cells_skipped() -> None:
    bundle = _bundle_with([
        [None],
        ["IO No"],
        ["IO-3"],
        [None],
        [""],
        ["IO-6"],
    ])
    findings = IoNumberComponent().extract_findings(bundle)
    assert [f.value for f in findings] == ["IO-3", "IO-6"]


def test_each_finding_carries_io_number_canonical() -> None:
    bundle = _bundle_with([[None], ["IO No"], ["X-1"]])
    findings = IoNumberComponent().extract_findings(bundle)
    assert findings[0].canonical == "io_number"


def test_extractor_component_returns_findings_dict() -> None:
    bundle = _bundle_with([[None], ["IO No"], ["X-1"], ["X-2"]])
    out = IoNumberExtractor().run(bundle=bundle)
    assert set(out.keys()) == {"findings"}
    assert [f.value for f in out["findings"]] == ["X-1", "X-2"]


def test_extractor_component_sockets_registered() -> None:
    comp = IoNumberExtractor()
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "findings" in comp.__haystack_output__._sockets_dict


def test_extractor_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("io_extractor", IoNumberExtractor())
    assert "io_extractor" in pipeline.graph.nodes
