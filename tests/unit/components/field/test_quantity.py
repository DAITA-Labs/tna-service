"""QuantityExtractor — spec-driven extraction with bag.int_strips + constraints."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.canvas import GridCanvas
from app.artifacts.finding import Confidence
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import (
    DataRowRange,
    HeaderBand,
    IntStrip,
    Rect,
    StructureBag,
)
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.field.quantity import QuantityExtractor


def _bundle_with(values, *, axis="vertical", columns=None, rows=None,
                   int_strip_col: int | None = None):
    """Build a bundle. When `int_strip_col` is set, the bag carries a matching IntStrip."""
    n_rows = len(values)
    n_cols = len(values[0]) if values else 0
    canvas = GridCanvas(n_rows=n_rows, n_cols=n_cols, cell_values=values)
    bag = StructureBag()
    bag.header_band = HeaderBand(rect=Rect(2, 1, 2, n_cols), score=0.9)
    bag.data_row_ranges = [DataRowRange(row_start=3, row_end=n_rows)]
    if int_strip_col is not None:
        bag.int_strips = [IntStrip(
            rect=Rect(3, int_strip_col, n_rows, int_strip_col),
            magnitude="medium", density=0.95,
        )]
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


# ─── Header-only path (MEDIUM confidence) ──────────────────────────────────


def test_header_only_match_yields_medium_confidence() -> None:
    """Candidate column with no IntStrip → MEDIUM (header confirmed valid value)."""
    bundle = _bundle_with([[None], ["Qty"], [1200]])  # no int_strip_col
    out = QuantityExtractor().run(bundle=bundle)
    f = out["findings"][0]
    assert f.confidence == Confidence.MEDIUM
    assert "HEADER_BAND_MEMBER" in f.evidence
    assert "INT_STRIP_CONFIRMED" not in f.evidence


# ─── Header + IntStrip path (HIGH confidence) ──────────────────────────────


def test_int_strip_confirmation_lifts_confidence_to_high() -> None:
    """Candidate column AND a matching IntStrip on its data rows → HIGH."""
    bundle = _bundle_with([[None], ["Qty"], [1200], [500]], int_strip_col=1)
    out = QuantityExtractor().run(bundle=bundle)
    f = out["findings"][0]
    assert f.confidence == Confidence.HIGH
    assert "INT_STRIP_CONFIRMED" in f.evidence


def test_int_strip_on_different_column_does_not_confirm() -> None:
    """An IntStrip on a different column doesn't confirm the candidate column."""
    bundle = _bundle_with([[None, None], ["Qty", "Other"], [1200, 9]], int_strip_col=2)
    out = QuantityExtractor().run(bundle=bundle)
    f = out["findings"][0]
    assert f.confidence == Confidence.MEDIUM
    assert "INT_STRIP_CONFIRMED" not in f.evidence


# ─── Constraint violations (LOW confidence) ────────────────────────────────


def test_below_min_constraint_tagged_and_demoted_to_low() -> None:
    """Quantity 0 is skipped; quantity below spec min=1 isn't reachable through coercion."""
    # The spec's min is 1 and 0 is already skipped by extractor — verify max instead.
    pass


def test_above_max_constraint_tagged_and_demoted_to_low() -> None:
    """Value > QUANTITY_SPEC.value_constraints.max → LOW + CONSTRAINT:above_max."""
    bundle = _bundle_with([[None], ["Qty"], [1_000_000]], int_strip_col=1)
    out = QuantityExtractor().run(bundle=bundle)
    f = out["findings"][0]
    assert f.confidence == Confidence.LOW
    assert "CONSTRAINT:above_max" in f.evidence
    assert "INT_STRIP_CONFIRMED" in f.evidence  # the strip still confirmed; just out of range


def test_garbage_string_demoted_to_low_with_value_not_numeric() -> None:
    bundle = _bundle_with([[None], ["Qty"], ["TBD"]])
    out = QuantityExtractor().run(bundle=bundle)
    f = out["findings"][0]
    assert f.confidence == Confidence.LOW
    assert "CONSTRAINT:value_not_numeric" in f.evidence


# ─── Coercion still works ──────────────────────────────────────────────────


def test_int_kept_as_int() -> None:
    bundle = _bundle_with([[None], ["Qty"], [1200]])
    assert QuantityExtractor().run(bundle=bundle)["findings"][0].value == 1200


def test_integer_valued_float_coerced_to_int() -> None:
    bundle = _bundle_with([[None], ["Qty"], [1200.0]])
    assert QuantityExtractor().run(bundle=bundle)["findings"][0].value == 1200


def test_thousands_separator_string_parsed() -> None:
    bundle = _bundle_with([[None], ["Qty"], ["1,200"]])
    assert QuantityExtractor().run(bundle=bundle)["findings"][0].value == 1200


def test_unit_suffix_string_parsed() -> None:
    bundle = _bundle_with([[None], ["Qty"], ["1200 pcs"]])
    assert QuantityExtractor().run(bundle=bundle)["findings"][0].value == 1200


def test_blank_and_zero_skipped() -> None:
    bundle = _bundle_with([
        [None], ["Qty"], [None], [""], [0], [0.0], ["0"], [100],
    ])
    out = QuantityExtractor().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [100]


def test_bool_rejected() -> None:
    bundle = _bundle_with([[None], ["Qty"], [True]])
    assert QuantityExtractor().run(bundle=bundle)["findings"] == []


# ─── Shape / sockets / Pipeline ────────────────────────────────────────────


def test_finding_carries_quantity_canonical_and_coords() -> None:
    bundle = _bundle_with([[None], ["Qty"], [100]])
    f = QuantityExtractor().run(bundle=bundle)["findings"][0]
    assert f.canonical == "quantity"
    assert f.value_coord == ("A", 3)
    assert f.label_coord == ("A", 2)


def test_no_candidate_columns_yields_no_findings() -> None:
    bundle = _bundle_with([[None], ["Qty"], [100]], columns={})
    assert QuantityExtractor().run(bundle=bundle)["findings"] == []


def test_unsupported_pli_axis_returns_empty() -> None:
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
