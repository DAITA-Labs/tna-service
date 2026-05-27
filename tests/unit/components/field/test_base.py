"""BaseCanonicalExtractor — ROW_PER_PLI extraction harness."""
from __future__ import annotations

from haystack import component

from app.artifacts.canvas import GridCanvas
from app.artifacts.finding import Confidence
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import DataRowRange, HeaderBand, Rect, StructureBag
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.field._base import BaseCanonicalExtractor


@component
class _DummyExtractor(BaseCanonicalExtractor):
    """Test-only subclass — extracts a 'dummy_id' canonical."""
    canonical = "dummy_id"


def _bundle(*, axis="vertical", canvas_values=None, columns=None, rows=None,
              header_band_rect=Rect(2, 1, 2, 4)) -> ClusterAnchorBundle:
    """Build a minimal ClusterAnchorBundle for the harness."""
    n_rows = max(len(canvas_values or [[]]), 5)
    n_cols = max((len(canvas_values[0]) if canvas_values else 4), 4)
    canvas = GridCanvas(
        n_rows=n_rows, n_cols=n_cols,
        cell_values=canvas_values or [[None] * n_cols for _ in range(n_rows)],
    )
    bag = StructureBag()
    bag.header_band = HeaderBand(rect=header_band_rect, score=0.9)
    bag.data_row_ranges = [DataRowRange(row_start=3, row_end=7)]
    hint = LayoutHint(
        axes=LayoutAxes(pli_axis=axis, stage_axis="none", subfield_axis="implicit"),
        cluster_id="c0", confidence=0.9,
        header_band=bag.header_band,
        data_row_ranges=bag.data_row_ranges,
        candidate_columns=columns or {},
        candidate_rows=rows or {},
    )
    return ClusterAnchorBundle(
        cluster=PliCluster(cluster_id="c0", sheet_names=["S"], role="pli_cluster"),
        anchor_sheet_name="S",
        canvas=canvas, bag=bag, hint=hint,
    )


def test_subclass_without_canonical_raises() -> None:
    """Calling run without setting `canonical` raises NotImplementedError."""
    @component
    class _BlankSubclass(BaseCanonicalExtractor):
        pass

    import pytest
    with pytest.raises(NotImplementedError):
        _BlankSubclass().run(bundle=_bundle())


def test_vertical_pli_emits_one_finding_per_non_blank_row() -> None:
    """5 data rows of which 4 are populated → 4 findings."""
    values = [
        [None] * 4,        # row 1
        ["IO No"] + [None] * 3,  # row 2 — header
        ["IO-3"] + [None] * 3,   # row 3
        ["IO-4"] + [None] * 3,
        ["IO-5"] + [None] * 3,
        [None] * 4,        # row 6 blank
        ["IO-7"] + [None] * 3,
    ]
    bundle = _bundle(
        canvas_values=values,
        columns={"dummy_id": [1]},
        rows={"dummy_id": [3, 4, 5, 6, 7]},
    )
    out = _DummyExtractor().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == ["IO-3", "IO-4", "IO-5", "IO-7"]


def test_findings_carry_canonical_and_coords() -> None:
    values = [[None, None], [None, None], ["X-1", None]]
    bundle = _bundle(
        canvas_values=values,
        columns={"dummy_id": [1]},
        rows={"dummy_id": [3]},
        header_band_rect=Rect(2, 1, 2, 2),
    )
    out = _DummyExtractor().run(bundle=bundle)
    f = out["findings"][0]
    assert f.canonical == "dummy_id"
    assert f.value_coord == ("A", 3)
    assert f.label_coord == ("A", 2)
    assert f.confidence == Confidence.MEDIUM
    assert "HEADER_BAND_MEMBER" in f.evidence


def test_no_candidate_columns_yields_no_findings() -> None:
    values = [[None] * 2, [None] * 2, ["X-1", None]]
    bundle = _bundle(canvas_values=values, columns={}, rows={"dummy_id": [3]})
    assert _DummyExtractor().run(bundle=bundle)["findings"] == []


def test_no_candidate_rows_yields_no_findings() -> None:
    values = [[None] * 2, [None] * 2, ["X-1", None]]
    bundle = _bundle(canvas_values=values, columns={"dummy_id": [1]}, rows={})
    assert _DummyExtractor().run(bundle=bundle)["findings"] == []


def test_unsupported_pli_axis_returns_empty_list() -> None:
    """Sectional / sheet / horizontal axes return [] until implemented."""
    values = [[None] * 2, ["IO", None], ["X-1", None]]
    for axis in ("sectional", "sheet", "horizontal"):
        bundle = _bundle(
            axis=axis, canvas_values=values,
            columns={"dummy_id": [1]}, rows={"dummy_id": [3]},
        )
        assert _DummyExtractor().run(bundle=bundle)["findings"] == []


def test_postprocess_hook_applied_to_each_value() -> None:
    """Subclass can override _postprocess to coerce values."""
    @component
    class _UpperCaser(BaseCanonicalExtractor):
        canonical = "dummy_id"

        def _postprocess(self, value):
            return value.upper()

    values = [[None] * 2, [None] * 2, ["io-3", None]]
    bundle = _bundle(
        canvas_values=values,
        columns={"dummy_id": [1]},
        rows={"dummy_id": [3]},
    )
    out = _UpperCaser().run(bundle=bundle)
    assert out["findings"][0].value == "IO-3"


def test_extractor_sockets_registered() -> None:
    """Concrete subclass exposes bundle input + findings output sockets."""
    comp = _DummyExtractor()
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "findings" in comp.__haystack_output__._sockets_dict


def test_extractor_addable_to_pipeline() -> None:
    from haystack import Pipeline
    pipeline = Pipeline()
    pipeline.add_component("dummy", _DummyExtractor())
    assert "dummy" in pipeline.graph.nodes
