"""StyleName / ColorName / FabricName extractors — shared parametric tests."""
from __future__ import annotations

import pytest
from haystack import Pipeline

from app.artifacts.canvas import GridCanvas
from app.artifacts.finding import Confidence
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import (
    DataRowRange,
    HeaderBand,
    LongTextStrip,
    Rect,
    StructureBag,
)
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.field.color_name import ColorNameExtractor
from app.components.field.fabric_name import FabricNameExtractor
from app.components.field.style_name import StyleNameExtractor


NAME_EXTRACTORS = [
    (StyleNameExtractor, "style_name"),
    (ColorNameExtractor, "color_name"),
    (FabricNameExtractor, "fabric_name"),
]


def _bundle_with(values, canonical, *, axis="vertical", columns=None, rows=None,
                   long_text_col: int | None = None):
    """Build a bundle. When `long_text_col` is set, bag carries a matching LongTextStrip."""
    n_rows = len(values)
    n_cols = len(values[0]) if values else 0
    canvas = GridCanvas(n_rows=n_rows, n_cols=n_cols, cell_values=values)
    bag = StructureBag()
    bag.header_band = HeaderBand(rect=Rect(2, 1, 2, n_cols), score=0.9)
    bag.data_row_ranges = [DataRowRange(row_start=3, row_end=n_rows)]
    if long_text_col is not None:
        bag.long_text_strips = [LongTextStrip(
            rect=Rect(3, long_text_col, n_rows, long_text_col),
            mean_length=30.0,
        )]
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


@pytest.mark.parametrize("extractor_cls,canonical", NAME_EXTRACTORS)
def test_descriptive_names_extracted_with_whitespace_stripped(extractor_cls, canonical) -> None:
    bundle = _bundle_with([
        [None], ["Hdr"],
        ["  TAVIRA WIDE LEG JEAN  "],
        ["100% cotton single jersey"],
    ], canonical)
    out = extractor_cls().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [
        "TAVIRA WIDE LEG JEAN", "100% cotton single jersey",
    ]


@pytest.mark.parametrize("extractor_cls,canonical", NAME_EXTRACTORS)
def test_numeric_cells_coerced_to_string_via_str(extractor_cls, canonical) -> None:
    """openpyxl may type a purely-numeric description as int; coerce defensively."""
    bundle = _bundle_with([[None], ["Hdr"], [12345]], canonical)
    out = extractor_cls().run(bundle=bundle)
    assert out["findings"][0].value == "12345"


@pytest.mark.parametrize("extractor_cls,canonical", NAME_EXTRACTORS)
def test_blank_cells_skipped(extractor_cls, canonical) -> None:
    bundle = _bundle_with([
        [None], ["Hdr"], ["FIRST"], [None], [""], ["FOURTH"],
    ], canonical)
    out = extractor_cls().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == ["FIRST", "FOURTH"]


@pytest.mark.parametrize("extractor_cls,canonical", NAME_EXTRACTORS)
def test_finding_carries_correct_canonical_and_coords(extractor_cls, canonical) -> None:
    bundle = _bundle_with([[None], ["Hdr"], ["NAME"]], canonical)
    out = extractor_cls().run(bundle=bundle)
    f = out["findings"][0]
    assert f.canonical == canonical
    assert f.value_coord == ("A", 3)
    assert f.label_coord == ("A", 2)
    assert "HEADER_BAND_MEMBER" in f.evidence


# ─── confidence ladder ─────────────────────────────────────────────────────


@pytest.mark.parametrize("extractor_cls,canonical", NAME_EXTRACTORS)
def test_header_only_match_yields_medium_confidence(extractor_cls, canonical) -> None:
    """Candidate column with no LongTextStrip → MEDIUM."""
    bundle = _bundle_with([[None], ["Hdr"], ["TAVIRA WIDE LEG JEAN"]], canonical)
    f = extractor_cls().run(bundle=bundle)["findings"][0]
    assert f.confidence == Confidence.MEDIUM
    assert "LONG_TEXT_STRIP_CONFIRMED" not in f.evidence


@pytest.mark.parametrize("extractor_cls,canonical", NAME_EXTRACTORS)
def test_long_text_strip_confirmation_lifts_to_high(extractor_cls, canonical) -> None:
    """Candidate column + matching LongTextStrip → HIGH with confirmation tag."""
    bundle = _bundle_with(
        [[None], ["Hdr"], ["TAVIRA WIDE LEG JEAN"], ["DARK MIDNIGHT BLUE"]],
        canonical, long_text_col=1,
    )
    f = extractor_cls().run(bundle=bundle)["findings"][0]
    assert f.confidence == Confidence.HIGH
    assert "LONG_TEXT_STRIP_CONFIRMED" in f.evidence


@pytest.mark.parametrize("extractor_cls,canonical", NAME_EXTRACTORS)
def test_long_text_strip_in_different_column_does_not_confirm(extractor_cls, canonical) -> None:
    """A LongTextStrip on a different column doesn't confirm the candidate column."""
    bundle = _bundle_with(
        [[None, None], ["Hdr", "Other"], ["NAME", "irrelevant"]],
        canonical, long_text_col=2,
    )
    f = extractor_cls().run(bundle=bundle)["findings"][0]
    assert f.confidence == Confidence.MEDIUM
    assert "LONG_TEXT_STRIP_CONFIRMED" not in f.evidence


@pytest.mark.parametrize("extractor_cls,canonical", NAME_EXTRACTORS)
def test_no_candidate_columns_yields_no_findings(extractor_cls, canonical) -> None:
    """When the sheet has only a *_code column (no name column), the name extractor emits nothing."""
    bundle = _bundle_with([[None], ["Hdr"], ["NAME"]], canonical, columns={})
    assert extractor_cls().run(bundle=bundle)["findings"] == []


@pytest.mark.parametrize("extractor_cls,canonical", NAME_EXTRACTORS)
def test_unsupported_pli_axis_returns_empty(extractor_cls, canonical) -> None:
    for axis in ("sectional", "sheet", "horizontal"):
        bundle = _bundle_with([[None], ["Hdr"], ["NAME"]], canonical, axis=axis)
        assert extractor_cls().run(bundle=bundle)["findings"] == []


@pytest.mark.parametrize("extractor_cls,_canonical", NAME_EXTRACTORS)
def test_extractor_sockets_registered(extractor_cls, _canonical) -> None:
    comp = extractor_cls()
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "findings" in comp.__haystack_output__._sockets_dict


@pytest.mark.parametrize("extractor_cls,canonical", NAME_EXTRACTORS)
def test_extractor_addable_to_pipeline(extractor_cls, canonical) -> None:
    pipeline = Pipeline()
    pipeline.add_component(canonical, extractor_cls())
    assert canonical in pipeline.graph.nodes
