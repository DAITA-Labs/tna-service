"""Shared bundle helpers for field-extractor tests.

Field extractors consume a `ClusterAnchorBundle`. Building one by hand
requires:
  - a GridCanvas with both cell_values AND a `dtype` channel (the
    column scorer reads cells via the dtype channel, so tests must
    derive it from the cell values to match what `run_structure_phase`
    would produce)
  - a StructureBag with the optional strip records each extractor uses
  - a LayoutHint pointing at the canonical's candidate columns and rows

`make_bundle` collapses that boilerplate. Tests pass cell values and
optional strip records; the helper handles the rest.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import (
    DataRowRange,
    DateStrip,
    HeaderBand,
    IntStrip,
    KvBlock,
    LongTextStrip,
    Rect,
    SameLengthStrip,
    StructureBag,
)
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster


# Canvas dtype channel codes — mirror app.tools.canvas.build.
_BLANK, _DATE, _INT, _FLOAT, _STR = 0, 1, 2, 3, 4


def _classify_dtype(value: Any) -> int:
    """Map a cell value to the canvas's dtype-channel code."""
    if value is None or value == "":
        return _BLANK
    if isinstance(value, bool):
        return _INT
    if isinstance(value, (dt.datetime, dt.date)):
        return _DATE
    if isinstance(value, int):
        return _INT
    if isinstance(value, float):
        return _FLOAT
    return _STR


def make_bundle(values: list[list[Any]],
                 canonical: str,
                 *,
                 axis: str = "vertical",
                 columns: dict[str, list[int]] | None = None,
                 rows: dict[str, list[int]] | None = None,
                 int_strip_col: int | None = None,
                 date_strip_col: int | None = None,
                 same_length_strip_col: int | None = None,
                 long_text_strip_col: int | None = None,
                 candidate_kv_blocks: dict[str, list[KvBlock]] | None = None,
                 merge_ranges: set[tuple[int, int, int, int]] | None = None,
                 ) -> ClusterAnchorBundle:
    """Construct a ClusterAnchorBundle for extractor tests.

    The canvas's `dtype` channel is auto-derived from the cell values
    so the column scorer can evaluate dtype_match_rate. Strip records
    are populated when the corresponding `*_strip_col` argument is set.
    """
    n_rows = len(values)
    n_cols = len(values[0]) if values else 0
    dtype_channel = [[_classify_dtype(v) for v in row] for row in values]
    canvas = GridCanvas(
        n_rows=n_rows, n_cols=n_cols, cell_values=values,
        channels={"dtype": dtype_channel},
        merge_ranges=merge_ranges or set(),
    )

    bag = StructureBag()
    bag.header_band = HeaderBand(rect=Rect(2, 1, 2, n_cols), score=0.9)
    bag.data_row_ranges = [DataRowRange(row_start=3, row_end=n_rows)]
    if int_strip_col is not None:
        bag.int_strips = [IntStrip(
            rect=Rect(3, int_strip_col, n_rows, int_strip_col),
            magnitude="medium", density=0.95,
        )]
    if date_strip_col is not None:
        bag.date_strips = [DateStrip(
            rect=Rect(3, date_strip_col, n_rows, date_strip_col),
            orientation="vertical", density=1.0,
        )]
    if same_length_strip_col is not None:
        bag.same_length_strips = [SameLengthStrip(
            rect=Rect(3, same_length_strip_col, n_rows, same_length_strip_col),
            length=6, density=1.0,
        )]
    if long_text_strip_col is not None:
        bag.long_text_strips = [LongTextStrip(
            rect=Rect(3, long_text_strip_col, n_rows, long_text_strip_col),
            mean_length=30.0,
        )]

    hint = LayoutHint(
        axes=LayoutAxes(pli_axis=axis, stage_axis="none", subfield_axis="implicit"),
        cluster_id="c0", confidence=0.9,
        header_band=bag.header_band,
        data_row_ranges=bag.data_row_ranges,
        candidate_columns=columns if columns is not None else {canonical: [1]},
        candidate_rows=rows if rows is not None else {canonical: list(range(3, n_rows + 1))},
        candidate_kv_blocks=candidate_kv_blocks or {},
    )
    return ClusterAnchorBundle(
        cluster=PliCluster(cluster_id="c0", sheet_names=["S"], role="pli_cluster"),
        anchor_sheet_name="S", canvas=canvas, bag=bag, hint=hint,
    )
