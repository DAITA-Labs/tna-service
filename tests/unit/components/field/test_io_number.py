"""IoNumberExtractor — io_number extraction + Haystack wiring."""
from __future__ import annotations

from haystack import Pipeline

from app.components.field.io_number import IoNumberExtractor
from tests.unit.components.field._bundles import make_bundle


def _bundle_with(values, *, axis="vertical", columns=None, rows=None,
                   same_length_strip_col=None):
    return make_bundle(
        values, "io_number",
        axis=axis, columns=columns, rows=rows,
        same_length_strip_col=same_length_strip_col,
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
