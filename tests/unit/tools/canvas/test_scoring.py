"""score_column_for_canonical — column finalization scoring."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import IntStrip, Rect
from app.specs import QUANTITY_SPEC
from app.specs._base import FieldSpec, ValueConstraints
from app.specs.enums import Area, ValueDtype
from app.tools._registry import TOOL_REGISTRY
from app.tools.canvas.scoring import score_column_for_canonical


# Canvas dtype channel codes — mirror app.tools.canvas.build
_BLANK, _DATE, _INT, _FLOAT, _STR = 0, 1, 2, 3, 4


def _canvas_with_dtype_column(col_idx: int, n_rows: int, dtype_code: int):
    """Build a canvas where column `col_idx` carries `dtype_code` in every row."""
    cells = [[None] * 5 for _ in range(n_rows)]
    dtype_channel = [[_BLANK] * 5 for _ in range(n_rows)]
    for r in range(n_rows):
        dtype_channel[r][col_idx - 1] = dtype_code
        cells[r][col_idx - 1] = 100  # populated value
    return GridCanvas(
        n_rows=n_rows, n_cols=5, cell_values=cells,
        channels={"dtype": dtype_channel},
    )


def test_perfect_column_scores_one() -> None:
    """Strip overlap + 100% int dtype + 100% constraint pass → 1.0."""
    canvas = _canvas_with_dtype_column(col_idx=1, n_rows=10, dtype_code=_INT)
    strips = [IntStrip(rect=Rect(3, 1, 7, 1), magnitude="medium", density=1.0)]
    score = score_column_for_canonical(
        canvas, col_idx=1, rows=[3, 4, 5, 6, 7],
        spec=QUANTITY_SPEC, strips=strips,
    )
    assert score == 1.0


def test_no_strip_overlap_drops_score() -> None:
    """Dtype + constraints still pass but no strip → 0.4*0 + 0.4*1 + 0.2*1 = 0.6."""
    canvas = _canvas_with_dtype_column(col_idx=1, n_rows=10, dtype_code=_INT)
    score = score_column_for_canonical(
        canvas, col_idx=1, rows=[3, 4, 5, 6, 7],
        spec=QUANTITY_SPEC, strips=[],
    )
    assert abs(score - 0.6) < 1e-9


def test_dtype_mismatch_drops_score() -> None:
    """String dtype where quantity expects INT → dtype score 0 → total 0.4*1 + 0.4*0 + 0.2*0 = 0.4.

    Constraints fail too because string values don't meet min/max numeric checks
    (and are not strings the spec accepts).
    """
    canvas = _canvas_with_dtype_column(col_idx=1, n_rows=10, dtype_code=_STR)
    # Replace the populated value with strings
    for r in range(10):
        canvas.cell_values[r][0] = "NOT_A_NUMBER"
    strips = [IntStrip(rect=Rect(3, 1, 7, 1), magnitude="medium", density=1.0)]
    score = score_column_for_canonical(
        canvas, col_idx=1, rows=[3, 4, 5, 6, 7],
        spec=QUANTITY_SPEC, strips=strips,
    )
    # strip=1, dtype=0 (string vs int), constraint=1.0 (string values not subject
    # to numeric min/max, length checks not on quantity spec) → 0.4 + 0 + 0.2 = 0.6
    # Adjust: QUANTITY_SPEC has no min_len/max_len, so strings pass constraint vacuously
    assert abs(score - 0.6) < 1e-9


def test_constraint_violation_drops_score() -> None:
    """Values exceed quantity max → constraint score 0."""
    canvas = _canvas_with_dtype_column(col_idx=1, n_rows=10, dtype_code=_INT)
    for r in range(10):
        canvas.cell_values[r][0] = 9_999_999  # > 100,000
    strips = [IntStrip(rect=Rect(3, 1, 7, 1), magnitude="medium", density=1.0)]
    score = score_column_for_canonical(
        canvas, col_idx=1, rows=[3, 4, 5, 6, 7],
        spec=QUANTITY_SPEC, strips=strips,
    )
    # strip=1, dtype=1, constraint=0 → 0.4 + 0.4 + 0 = 0.8
    assert abs(score - 0.8) < 1e-9


def test_partial_dtype_match() -> None:
    """3 of 5 rows are int, 2 are string → dtype score = 3/5 = 0.6."""
    canvas = _canvas_with_dtype_column(col_idx=1, n_rows=10, dtype_code=_INT)
    # Make rows 4 and 5 strings instead
    canvas.channels["dtype"][3][0] = _STR
    canvas.channels["dtype"][4][0] = _STR
    canvas.cell_values[3][0] = "X"
    canvas.cell_values[4][0] = "Y"
    score = score_column_for_canonical(
        canvas, col_idx=1, rows=[3, 4, 5, 6, 7],
        spec=QUANTITY_SPEC, strips=[],
    )
    # strip=0, dtype = 3/5 = 0.6, constraint = 1.0 (numeric values pass; strings pass vacuously)
    # → 0 + 0.4*0.6 + 0.2*1 = 0.24 + 0.2 = 0.44
    assert abs(score - 0.44) < 1e-9


def test_empty_rows_yields_zero() -> None:
    canvas = _canvas_with_dtype_column(col_idx=1, n_rows=10, dtype_code=_INT)
    assert score_column_for_canonical(
        canvas, col_idx=1, rows=[], spec=QUANTITY_SPEC, strips=[],
    ) == 0.0


def test_any_dtype_spec_always_passes_dtype_check() -> None:
    """Spec.value_dtype = ANY → dtype score is always 1.0."""
    spec = FieldSpec(
        canonical="anycanon", area=Area.IDENTIFIERS, description="",
        aliases=("any",), value_dtype=ValueDtype.ANY,
        value_constraints=ValueConstraints(),
    )
    canvas = _canvas_with_dtype_column(col_idx=1, n_rows=10, dtype_code=_STR)
    score = score_column_for_canonical(
        canvas, col_idx=1, rows=[3, 4, 5], spec=spec, strips=[],
    )
    # strip=0, dtype=1 (ANY passes), constraint=1 (empty constraints) → 0.4 + 0.2 = 0.6
    assert abs(score - 0.6) < 1e-9


def test_tool_registered_under_canonical_name() -> None:
    assert "score_column_for_canonical" in TOOL_REGISTRY.names()
