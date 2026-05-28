"""QuantityDtypeValidator — sanity-check the picked quantity column.

Two independent checks against the column the extractor named as
`quantity`, both gated at 80% of the column's non-blank PLI-row cells:

  1. numeric density       — ≥80% of cells are int/float
  2. value-range coverage  — ≥80% of numeric cells lie in [1, 100000]

When either ratio falls below the threshold, the column probably
isn't actually carrying garment counts — the extractor likely picked
a sibling identifier column by mistake, or the source sheet stores
quantity as strings/formulas. Severity is `warning`; downstream
judges arbitrate.

Both thresholds and the expected value range live as module constants
for easy retuning once the eval scorecard runs on the canvas path.
"""
from __future__ import annotations

from collections import Counter

from haystack import component
from openpyxl.utils import column_index_from_string

from app.artifacts.finding import Finding, ValidationWarning
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component


_NUMERIC_DENSITY_THRESHOLD = 0.8
_VALUE_RANGE_MIN = 1
_VALUE_RANGE_MAX = 100_000
_VALUE_RANGE_THRESHOLD = 0.8


@component
class QuantityDtypeValidator(Component):
    """Emit warnings when the quantity column fails dtype or value-range checks."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(warnings=list[ValidationWarning])
    def run(self, findings: list[Finding], bundle: ClusterAnchorBundle) -> dict:
        warnings: list[ValidationWarning] = []
        warnings.extend(_check_numeric_density(findings, bundle))
        warnings.extend(_check_value_in_expected_range(findings, bundle))
        return {"warnings": warnings}


def _check_numeric_density(
    findings: list[Finding],
    bundle: ClusterAnchorBundle,
) -> list[ValidationWarning]:
    """Flag when <80% of the quantity column's non-blank cells are int/float."""
    col = _quantity_column(findings)
    if col is None:
        return []

    non_blank = [v for v in _quantity_column_cells(bundle, col) if _is_filled(v)]
    if not non_blank:
        return []

    numeric_count = sum(1 for v in non_blank if _is_numeric(v))
    density = numeric_count / len(non_blank)
    if density >= _NUMERIC_DENSITY_THRESHOLD:
        return []

    return [ValidationWarning(
        name="quantity_column_low_numeric_density",
        severity="warning",
        message=(
            f"Quantity column has only {numeric_count}/{len(non_blank)} numeric "
            f"cells ({density:.0%}) — below the {_NUMERIC_DENSITY_THRESHOLD:.0%} "
            f"threshold. The extractor likely picked a non-quantity column."
        ),
    )]


def _check_value_in_expected_range(
    findings: list[Finding],
    bundle: ClusterAnchorBundle,
) -> list[ValidationWarning]:
    """Flag when <80% of the quantity column's numeric cells lie in [1, 100000]."""
    col = _quantity_column(findings)
    if col is None:
        return []

    numeric = [v for v in _quantity_column_cells(bundle, col) if _is_numeric(v)]
    if not numeric:
        return []

    in_range = sum(1 for v in numeric if _VALUE_RANGE_MIN <= v <= _VALUE_RANGE_MAX)
    density = in_range / len(numeric)
    if density >= _VALUE_RANGE_THRESHOLD:
        return []

    return [ValidationWarning(
        name="quantity_column_out_of_range_values",
        severity="warning",
        message=(
            f"Quantity column has {in_range}/{len(numeric)} values in "
            f"[{_VALUE_RANGE_MIN}, {_VALUE_RANGE_MAX}] ({density:.0%}) — below "
            f"the {_VALUE_RANGE_THRESHOLD:.0%} threshold. Values outside this "
            f"range suggest the column carries IDs, codes, or sums rather "
            f"than garment counts."
        ),
    )]


def _quantity_column(findings: list[Finding]) -> int | None:
    """Return the 1-indexed column where quantity findings concentrate."""
    cols = [
        column_index_from_string(f.value_coord[0])
        for f in findings if f.canonical == "quantity"
    ]
    if not cols:
        return None
    return Counter(cols).most_common(1)[0][0]


def _quantity_column_cells(bundle: ClusterAnchorBundle, col: int) -> list[object]:
    """Read raw cell values in `col` across every PLI row range."""
    canvas = bundle.canvas
    if not (1 <= col <= canvas.n_cols):
        return []

    cells: list[object] = []
    for rng in bundle.hint.data_row_ranges:
        for row in range(rng.row_start, rng.row_end + 1):
            if 1 <= row <= canvas.n_rows:
                cells.append(canvas.cell_values[row - 1][col - 1])
    return cells


def _is_filled(value: object) -> bool:
    """True when the cell carries content — neither None nor the empty string."""
    return value is not None and value != ""


def _is_numeric(value: object) -> bool:
    """True for genuine int/float, excluding booleans (which are int subclasses)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)
