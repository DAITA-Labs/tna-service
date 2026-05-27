"""AxisInferrer — three orthogonal layout axes from canvas + StructureBag.

Emits a `LayoutAxes` record carrying:
  PliAxis      — vertical | sectional | sheet | horizontal | unknown
  StageAxis    — vertical | horizontal | none | unknown
  SubfieldAxis — vertical | horizontal | implicit | unknown

Decision rules (design spec §5.4):

  PliAxis:
    kv_blocks ≥ 3 AND n_data_rows < 5 AND sheet_size < 600 → sheet
    repeating_groups ≥ 3 AND n_data_rows ≥ 10              → sectional
    n_data_rows > n_data_cols * 2                          → vertical
    n_data_cols > n_data_rows * 2                          → horizontal
    else                                                    → vertical (conservative)

  StageAxis:
    PliAxis = sheet:
      horiz_date_strips ≥ 2  → horizontal (banded SHEET_IS_PLI)
      vert_date_strips ≥ 2   → vertical
      else                   → none
    PliAxis in (vertical, sectional):
      vert_date_strips ≥ 3   → horizontal (stage columns, walk right per PLI row)
      horiz_date_strips ≥ 3  → vertical
      else                   → none

  SubfieldAxis:
    inspect one StageBand:
      MergeSpan-Horiz above with 2-4 sub-columns of differing dtype → horizontal
      adjacent rows alternating string/date dtypes                  → vertical
    no bands → implicit
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes
from app.artifacts.structure import StructureBag
from app.tools.canvas.dtype_profiles import (
    compute_col_dtype_profiles,
    compute_row_dtype_profiles,
)


_KV_BLOCKS_FOR_SHEET = 3
_DATA_ROWS_MAX_FOR_SHEET = 5
_SHEET_SIZE_MAX = 600
_REPEATING_GROUPS_FOR_SECTIONAL = 3
_DATA_ROWS_MIN_FOR_SECTIONAL = 10
_AXIS_RATIO = 2.0
_DATE_STRIPS_FOR_SHEET_STAGE = 2
_DATE_STRIPS_FOR_TABULAR_STAGE = 3
_HIGH_CONFIDENCE = 0.9
_LOW_CONFIDENCE = 0.5


def infer_layout_axes(canvas: GridCanvas, bag: StructureBag) -> LayoutAxes:
    """Decide PliAxis / StageAxis / SubfieldAxis from canvas + bag signals.

    Returns a fresh LayoutAxes; does NOT mutate the bag.
    """
    n_data_rows, n_data_cols = _count_data_rows_and_cols(canvas)
    sheet_size = canvas.n_rows * canvas.n_cols
    kv_count = len(bag.kv_blocks)
    repeating_count = sum(1 for g in bag.repeating_groups if len(g.row_indices) >= 2)

    vert_dates, horiz_dates = _count_date_strip_orientations(bag)

    pli_axis, pli_conf = _decide_pli_axis(
        kv_count, repeating_count, n_data_rows, n_data_cols, sheet_size
    )
    stage_axis, stage_conf = _decide_stage_axis(pli_axis, vert_dates, horiz_dates)
    subfield_axis, subfield_conf = _decide_subfield_axis(canvas, bag)

    return LayoutAxes(
        pli_axis=pli_axis,
        stage_axis=stage_axis,
        subfield_axis=subfield_axis,
        confidence={
            "pli": pli_conf,
            "stage": stage_conf,
            "subfield": subfield_conf,
        },
    )


def _count_data_rows_and_cols(canvas: GridCanvas) -> tuple[int, int]:
    """Count rows/cols that look like data (non-blank, not pure-string-dominant)."""
    row_profiles = compute_row_dtype_profiles(canvas)
    col_profiles = compute_col_dtype_profiles(canvas)

    n_data_rows = sum(
        1 for p in row_profiles
        if (p.n_cols - p.n_blank) >= 3 and (p.n_str / max(1, p.n_cols)) < 0.5
    )
    n_data_cols = sum(
        1 for p in col_profiles
        if (p.n_rows - p.n_blank) >= 3 and (p.n_str / max(1, p.n_rows)) < 0.5
    )
    return n_data_rows, n_data_cols


def _count_date_strip_orientations(bag: StructureBag) -> tuple[int, int]:
    """Tally vertical vs horizontal date strips on the bag."""
    vert = sum(1 for s in bag.date_strips if s.orientation == "vertical")
    horiz = sum(1 for s in bag.date_strips if s.orientation == "horizontal")
    return vert, horiz


def _decide_pli_axis(kv: int,
                       repeating: int,
                       n_data_rows: int,
                       n_data_cols: int,
                       sheet_size: int) -> tuple[str, float]:
    """Apply the PliAxis decision tree; return (axis, confidence)."""
    if kv >= _KV_BLOCKS_FOR_SHEET and n_data_rows < _DATA_ROWS_MAX_FOR_SHEET \
            and sheet_size < _SHEET_SIZE_MAX:
        return "sheet", _HIGH_CONFIDENCE
    if repeating >= _REPEATING_GROUPS_FOR_SECTIONAL and n_data_rows >= _DATA_ROWS_MIN_FOR_SECTIONAL:
        return "sectional", _HIGH_CONFIDENCE
    if n_data_rows > n_data_cols * _AXIS_RATIO:
        return "vertical", _HIGH_CONFIDENCE
    if n_data_cols > n_data_rows * _AXIS_RATIO:
        return "horizontal", _HIGH_CONFIDENCE
    return "vertical", _LOW_CONFIDENCE


def _decide_stage_axis(pli_axis: str,
                         vert_dates: int,
                         horiz_dates: int) -> tuple[str, float]:
    """Apply the StageAxis decision tree; return (axis, confidence)."""
    if pli_axis == "sheet":
        if horiz_dates >= _DATE_STRIPS_FOR_SHEET_STAGE:
            return "horizontal", _HIGH_CONFIDENCE
        if vert_dates >= _DATE_STRIPS_FOR_SHEET_STAGE:
            return "vertical", _HIGH_CONFIDENCE
        return "none", _HIGH_CONFIDENCE
    if pli_axis in ("vertical", "sectional"):
        if vert_dates >= _DATE_STRIPS_FOR_TABULAR_STAGE:
            return "horizontal", _HIGH_CONFIDENCE
        if horiz_dates >= _DATE_STRIPS_FOR_TABULAR_STAGE:
            return "vertical", _HIGH_CONFIDENCE
        return "none", _LOW_CONFIDENCE
    return "unknown", _LOW_CONFIDENCE


def _decide_subfield_axis(canvas: GridCanvas, bag: StructureBag) -> tuple[str, float]:
    """Inspect one StageBand to decide whether sub-columns flow horizontally / vertically."""
    if not bag.stage_bands:
        return "implicit", _HIGH_CONFIDENCE

    band = bag.stage_bands[0]
    if any(span.orientation == "horizontal"
           and span.rect.r1 < band.rect.r0
           and span.rect.c0 <= band.rect.c1
           and span.rect.c1 >= band.rect.c0
           for span in bag.merge_spans):
        return "horizontal", _HIGH_CONFIDENCE
    return "horizontal", _LOW_CONFIDENCE
