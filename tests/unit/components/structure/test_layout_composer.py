"""LayoutComposer — assembling a LayoutHint from canvas + bag + axes."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes
from app.artifacts.structure import (
    DataRowRange,
    HeaderBand,
    KvBlock,
    Rect,
    StructureBag,
)
from app.components.structure.layout_composer import compose_layout_hint


def _canvas_with_header(label_row: int, label_col: int, text: str):
    """Build a minimal canvas with one identifier label cell."""
    n_rows, n_cols = 20, 20
    cells = [[None] * n_cols for _ in range(n_rows)]
    cells[label_row - 1][label_col - 1] = text
    return GridCanvas(n_rows=n_rows, n_cols=n_cols, cell_values=cells)


def _axes() -> LayoutAxes:
    return LayoutAxes(
        pli_axis="vertical",
        stage_axis="horizontal",
        subfield_axis="implicit",
        confidence={"pli": 0.9, "stage": 0.9, "subfield": 0.9},
    )


def test_layout_hint_carries_axes_and_records() -> None:
    """compose_layout_hint copies bag records onto the LayoutHint."""
    canvas = _canvas_with_header(1, 1, "ignored")
    bag = StructureBag()
    bag.header_band = HeaderBand(rect=Rect(2, 1, 3, 10), score=0.9)
    bag.data_row_ranges = [DataRowRange(row_start=4, row_end=20)]

    hint = compose_layout_hint(canvas, bag, _axes(), cluster_id="c0")
    assert hint.cluster_id == "c0"
    assert hint.axes.pli_axis == "vertical"
    assert hint.header_band is bag.header_band
    assert hint.data_row_ranges == [DataRowRange(row_start=4, row_end=20)]


def test_overall_confidence_averages_axis_confidences() -> None:
    """LayoutHint.confidence is the mean of LayoutAxes.confidence values."""
    canvas = _canvas_with_header(1, 1, "x")
    bag = StructureBag()
    axes = LayoutAxes(
        pli_axis="vertical", stage_axis="horizontal", subfield_axis="implicit",
        confidence={"pli": 0.9, "stage": 0.5, "subfield": 0.7},
    )
    hint = compose_layout_hint(canvas, bag, axes)
    assert abs(hint.confidence - 0.7) < 1e-9


def test_candidate_columns_per_canonical_pulled_from_header_band() -> None:
    """An identifier label cell inside the header band populates candidate_columns."""
    # Place 'Style' (style_code alias) at row 2, col 5 (= column 'E')
    canvas = _canvas_with_header(2, 5, "Style")
    bag = StructureBag()
    bag.header_band = HeaderBand(rect=Rect(2, 1, 3, 20), score=0.9)

    hint = compose_layout_hint(canvas, bag, _axes())
    assert "style_code" in hint.candidate_columns
    assert 5 in hint.candidate_columns["style_code"]


def test_candidate_columns_ranked_by_aggregate_match_weight() -> None:
    """A column with multiple matching header cells outranks a column with one.

    `query_spec` emits one match per alias-hit cell at a fixed per-spec
    weight. Aggregate per column = weight × matching-cell-count, so a
    multi-row header carrying the same canonical on two rows ranks above
    a single-cell match elsewhere.
    """
    n_rows, n_cols = 20, 20
    cells = [[None] * n_cols for _ in range(n_rows)]
    # Col 5 — single match on row 2
    cells[1][4] = "Style"
    # Col 10 — TWO matches across rows 2 + 3 (typical multi-row header)
    cells[1][9] = "Style"
    cells[2][9] = "Style Code"
    canvas = GridCanvas(n_rows=n_rows, n_cols=n_cols, cell_values=cells)
    bag = StructureBag()
    bag.header_band = HeaderBand(rect=Rect(2, 1, 3, 20), score=0.9)

    hint = compose_layout_hint(canvas, bag, _axes())
    ranked = hint.candidate_columns["style_code"]
    assert ranked[0] == 10, f"expected col 10 (2 hits) first, got {ranked}"
    assert 5 in ranked  # weaker match still present, just not first


def test_candidate_columns_tie_break_by_lower_column_index() -> None:
    """Equal aggregate weight → column with lower index wins (stable ordering)."""
    n_rows, n_cols = 20, 20
    cells = [[None] * n_cols for _ in range(n_rows)]
    cells[1][2] = "Style"   # col 3
    cells[1][7] = "Style"   # col 8 — same alias, same weight
    canvas = GridCanvas(n_rows=n_rows, n_cols=n_cols, cell_values=cells)
    bag = StructureBag()
    bag.header_band = HeaderBand(rect=Rect(2, 1, 2, 20), score=0.9)

    hint = compose_layout_hint(canvas, bag, _axes())
    ranked = hint.candidate_columns["style_code"]
    assert ranked == [3, 8]


def test_candidate_rows_share_data_row_range_when_tabular() -> None:
    """When there's a single tabular DataRowRange, every identifier gets those rows."""
    canvas = _canvas_with_header(1, 1, "x")
    bag = StructureBag()
    bag.data_row_ranges = [DataRowRange(row_start=4, row_end=10)]

    hint = compose_layout_hint(canvas, bag, _axes())
    rows = list(range(4, 11))
    assert hint.candidate_rows["io_number"] == rows
    assert hint.candidate_rows["quantity"] == rows
    assert hint.candidate_rows["delivery_date"] == rows


def test_candidate_kv_blocks_grouped_by_label_alias() -> None:
    """KvBlock label text is matched (case-insensitive substring) against alias hints."""
    canvas = _canvas_with_header(1, 1, "x")
    bag = StructureBag()
    bag.kv_blocks = [
        KvBlock(label_coord=("A", 4), value_coord=("B", 4),
                label_text="Job No", value_dtype=2),
        KvBlock(label_coord=("A", 5), value_coord=("B", 5),
                label_text="Total Qty", value_dtype=2),
        KvBlock(label_coord=("D", 4), value_coord=("E", 4),
                label_text="Ex-Factory Date", value_dtype=1),
    ]

    hint = compose_layout_hint(canvas, bag, _axes())
    assert any(kv.label_text == "Job No" for kv in hint.candidate_kv_blocks["io_number"])
    assert any(kv.label_text == "Total Qty" for kv in hint.candidate_kv_blocks["quantity"])
    assert any(kv.label_text == "Ex-Factory Date" for kv in hint.candidate_kv_blocks["ex_fty_date"])


def test_empty_bag_yields_empty_candidate_dicts() -> None:
    """A bag with no records yields empty candidate dicts (not KeyErrors)."""
    canvas = _canvas_with_header(1, 1, "x")
    bag = StructureBag()
    hint = compose_layout_hint(canvas, bag, _axes())
    assert hint.candidate_columns == {}
    assert hint.candidate_rows == {}
    assert hint.candidate_kv_blocks == {}
