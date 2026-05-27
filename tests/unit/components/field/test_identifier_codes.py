"""StyleCode / ColorCode / FabricCode extractors — shared parametric tests."""
from __future__ import annotations

import pytest
from haystack import Pipeline

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import DataRowRange, HeaderBand, Rect, StructureBag
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.field.color_code import ColorCodeExtractor
from app.components.field.fabric_code import FabricCodeExtractor
from app.components.field.style_code import StyleCodeExtractor


# (extractor_class, canonical_name) pairs — every identifier-code extractor follows the same shape.
CODE_EXTRACTORS = [
    (StyleCodeExtractor, "style_code"),
    (ColorCodeExtractor, "color_code"),
    (FabricCodeExtractor, "fabric_code"),
]


def _bundle_with(values, canonical, *, axis="vertical", columns=None, rows=None):
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
        candidate_columns=columns if columns is not None else {canonical: [1]},
        candidate_rows=rows if rows is not None else {canonical: list(range(3, n_rows + 1))},
    )
    return ClusterAnchorBundle(
        cluster=PliCluster(cluster_id="c0", sheet_names=["S"], role="pli_cluster"),
        anchor_sheet_name="S", canvas=canvas, bag=bag, hint=hint,
    )


@pytest.mark.parametrize("extractor_cls,canonical", CODE_EXTRACTORS)
def test_string_codes_stripped_of_whitespace(extractor_cls, canonical) -> None:
    bundle = _bundle_with([[None], ["Hdr"], [" CODE-3 "], ["CODE-4"]], canonical)
    out = extractor_cls().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == ["CODE-3", "CODE-4"]


@pytest.mark.parametrize("extractor_cls,canonical", CODE_EXTRACTORS)
def test_int_codes_coerced_to_str(extractor_cls, canonical) -> None:
    bundle = _bundle_with([[None], ["Hdr"], [1063], [1064]], canonical)
    out = extractor_cls().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == ["1063", "1064"]


@pytest.mark.parametrize("extractor_cls,canonical", CODE_EXTRACTORS)
def test_integer_valued_floats_drop_trailing_zero(extractor_cls, canonical) -> None:
    bundle = _bundle_with([[None], ["Hdr"], [1063.0], [1064.5]], canonical)
    out = extractor_cls().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == ["1063", "1064.5"]


@pytest.mark.parametrize("extractor_cls,canonical", CODE_EXTRACTORS)
def test_blank_cells_skipped(extractor_cls, canonical) -> None:
    bundle = _bundle_with([[None], ["Hdr"], ["X-1"], [None], [""], ["X-4"]], canonical)
    out = extractor_cls().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == ["X-1", "X-4"]


@pytest.mark.parametrize("extractor_cls,canonical", CODE_EXTRACTORS)
def test_finding_carries_correct_canonical_and_coords(extractor_cls, canonical) -> None:
    bundle = _bundle_with([[None], ["Hdr"], ["X-1"]], canonical)
    out = extractor_cls().run(bundle=bundle)
    f = out["findings"][0]
    assert f.canonical == canonical
    assert f.value_coord == ("A", 3)
    assert f.label_coord == ("A", 2)
    assert "HEADER_BAND_MEMBER" in f.evidence


@pytest.mark.parametrize("extractor_cls,canonical", CODE_EXTRACTORS)
def test_no_candidate_columns_yields_no_findings(extractor_cls, canonical) -> None:
    bundle = _bundle_with([[None], ["Hdr"], ["X-1"]], canonical, columns={})
    assert extractor_cls().run(bundle=bundle)["findings"] == []


@pytest.mark.parametrize("extractor_cls,canonical", CODE_EXTRACTORS)
def test_unsupported_pli_axis_returns_empty(extractor_cls, canonical) -> None:
    for axis in ("sectional", "sheet", "horizontal"):
        bundle = _bundle_with([[None], ["Hdr"], ["X-1"]], canonical, axis=axis)
        assert extractor_cls().run(bundle=bundle)["findings"] == []


@pytest.mark.parametrize("extractor_cls,_canonical", CODE_EXTRACTORS)
def test_extractor_sockets_registered(extractor_cls, _canonical) -> None:
    comp = extractor_cls()
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "findings" in comp.__haystack_output__._sockets_dict


@pytest.mark.parametrize("extractor_cls,canonical", CODE_EXTRACTORS)
def test_extractor_addable_to_pipeline(extractor_cls, canonical) -> None:
    pipeline = Pipeline()
    pipeline.add_component(canonical, extractor_cls())
    assert canonical in pipeline.graph.nodes
