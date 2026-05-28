"""QuantityDtypeValidator — numeric-density + value-range checks."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.components.validators.quantity_dtype import QuantityDtypeValidator
from tests.unit.components.field._bundles import make_bundle


def _bundle(values: list[list[object]]):
    """Build a bundle whose data_row_ranges cover rows 3..n_rows; quantity in col B."""
    return make_bundle(values, "quantity", columns={"quantity": [2]}, rows={})


def _f_qty(row: int, value: object = 100) -> Finding:
    """A quantity finding pointing at column B."""
    return Finding(
        canonical="quantity", label_coord=("B", 2),
        value_coord=("B", row), value=value,
        confidence=Confidence.HIGH, evidence=[],
    )


def _grid(rows: list[list[object]]):
    """Pad each row to 3 cols; prepend two header rows (data starts at row 3)."""
    padded = [[None, v, None] for v in [None] * 0] if False else [[None] * 3, [None] * 3]
    for row in rows:
        padded.append([None, row[0] if row else None, None])
    return padded


# ─── No-trigger paths ─────────────────────────────────────────────────────


def test_no_quantity_findings_no_warnings() -> None:
    """Without a quantity finding the validator can't locate the column."""
    bundle = _bundle(_grid([[100], [200], [300]]))
    assert QuantityDtypeValidator().run(findings=[], bundle=bundle)["warnings"] == []


def test_all_blank_column_no_warnings() -> None:
    """A quantity column with zero non-blank cells passes vacuously."""
    bundle = _bundle(_grid([[None], [None], [None]]))
    findings = [_f_qty(3)]
    assert QuantityDtypeValidator().run(findings=findings, bundle=bundle)["warnings"] == []


# ─── _check_numeric_density ───────────────────────────────────────────────


def test_all_numeric_in_range_no_warnings() -> None:
    bundle = _bundle(_grid([[100], [200], [300], [400], [500]]))
    findings = [_f_qty(r) for r in range(3, 8)]
    assert QuantityDtypeValidator().run(findings=findings, bundle=bundle)["warnings"] == []


def test_below_density_threshold_emits_warning() -> None:
    """6 numeric + 4 string = 60% numeric → density warning."""
    rows = [[100], [200], [300], [400], [500], [600], ["X"], ["Y"], ["Z"], ["W"]]
    bundle = _bundle(_grid(rows))
    findings = [_f_qty(r) for r in range(3, 9)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    density = [w for w in out["warnings"] if w.name == "quantity_column_low_numeric_density"]
    assert len(density) == 1
    assert density[0].severity == "warning"
    assert "6/10" in density[0].message
    assert "60%" in density[0].message


def test_density_at_exactly_80pct_no_warning() -> None:
    """8 numeric + 2 string = 80% — at the threshold, not below."""
    rows = [[100], [200], [300], [400], [500], [600], [700], [800], ["X"], ["Y"]]
    bundle = _bundle(_grid(rows))
    findings = [_f_qty(r) for r in range(3, 11)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if w.name == "quantity_column_low_numeric_density"] == []


def test_density_just_below_threshold_emits_warning() -> None:
    """7 numeric + 3 string = 70% — below threshold."""
    rows = [[100], [200], [300], [400], [500], [600], [700], ["X"], ["Y"], ["Z"]]
    bundle = _bundle(_grid(rows))
    findings = [_f_qty(r) for r in range(3, 10)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if w.name == "quantity_column_low_numeric_density"]


def test_blank_cells_not_counted_in_density() -> None:
    """Blanks are excluded from the denominator; 3 numeric / 3 non-blank = 100%."""
    rows = [[100], [None], [200], [None], [300]]
    bundle = _bundle(_grid(rows))
    findings = [_f_qty(3), _f_qty(5), _f_qty(7)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    assert out["warnings"] == []


def test_booleans_excluded_from_numeric() -> None:
    """Python booleans are int subclasses but shouldn't count as numeric quantities."""
    rows = [[True], [False], [True], [False], [100]]   # only 100 is "numeric"
    bundle = _bundle(_grid(rows))
    findings = [_f_qty(7, value=100)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if w.name == "quantity_column_low_numeric_density"]


def test_floats_count_as_numeric() -> None:
    rows = [[100.5], [200.0], [300.25], [400.0], [500.0]]
    bundle = _bundle(_grid(rows))
    findings = [_f_qty(r, value=100.0) for r in range(3, 8)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    assert out["warnings"] == []


# ─── _check_value_in_expected_range ───────────────────────────────────────


def test_all_in_range_no_warnings() -> None:
    bundle = _bundle(_grid([[1], [50], [1000], [99999], [100000]]))
    findings = [_f_qty(r) for r in range(3, 8)]
    assert QuantityDtypeValidator().run(findings=findings, bundle=bundle)["warnings"] == []


def test_value_zero_out_of_range() -> None:
    """0 is below the [1, 100000] range."""
    rows = [[0], [0], [0], [0], [0], [0], [0], [0], [100], [200]]   # 8 zero + 2 in-range = 20% in range
    bundle = _bundle(_grid(rows))
    findings = [_f_qty(r) for r in range(3, 13)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    range_warns = [w for w in out["warnings"] if w.name == "quantity_column_out_of_range_values"]
    assert len(range_warns) == 1
    assert "2/10" in range_warns[0].message
    assert "20%" in range_warns[0].message


def test_value_huge_out_of_range() -> None:
    """Year-like or aggregate values above 100,000 are out of range."""
    rows = [[10_000_000], [10_000_000], [10_000_000], [100], [200]]   # 2/5 in range = 40%
    bundle = _bundle(_grid(rows))
    findings = [_f_qty(r) for r in range(3, 8)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if w.name == "quantity_column_out_of_range_values"]


def test_value_negative_out_of_range() -> None:
    rows = [[-100], [-200], [-300], [-400], [50]]   # 1/5 in range
    bundle = _bundle(_grid(rows))
    findings = [_f_qty(r) for r in range(3, 8)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if w.name == "quantity_column_out_of_range_values"]


def test_range_check_boundary_inclusive() -> None:
    """1 and 100000 are both inside the inclusive range."""
    bundle = _bundle(_grid([[1], [100000], [50000], [200], [99999]]))
    findings = [_f_qty(r) for r in range(3, 8)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if w.name == "quantity_column_out_of_range_values"] == []


def test_range_check_ignores_non_numeric() -> None:
    """Strings are excluded from the range denominator (they fail the numeric check)."""
    rows = [[100], [200], [300], [400], [500], ["bad"], ["bad"]]   # 5 numeric all in range
    bundle = _bundle(_grid(rows))
    findings = [_f_qty(r) for r in range(3, 8)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if w.name == "quantity_column_out_of_range_values"] == []


# ─── Both checks together ────────────────────────────────────────────────


def test_both_checks_fire_independently() -> None:
    """Mostly strings AND the few numerics are out of range → both warnings emitted."""
    rows = [["X"], ["X"], ["X"], ["X"], ["X"], ["X"], ["X"], [9_999_999], [9_999_999]]
    bundle = _bundle(_grid(rows))
    findings = [_f_qty(r) for r in (10, 11)]
    out = QuantityDtypeValidator().run(findings=findings, bundle=bundle)
    names = sorted(w.name for w in out["warnings"])
    assert names == [
        "quantity_column_low_numeric_density",
        "quantity_column_out_of_range_values",
    ]


# ─── Quantity column resolution ──────────────────────────────────────────


def test_quantity_column_resolved_by_majority() -> None:
    """When findings span columns, the most common column wins."""
    bundle = _bundle(_grid([[100], [200], [300], [400], [500]]))
    findings = [
        _f_qty(3),
        Finding(canonical="quantity", label_coord=("C", 2),
                value_coord=("C", 4), value=200,
                confidence=Confidence.HIGH, evidence=[]),
        _f_qty(5), _f_qty(6), _f_qty(7),     # column B wins 4-1
    ]
    assert QuantityDtypeValidator().run(findings=findings, bundle=bundle)["warnings"] == []


# ─── Component plumbing ──────────────────────────────────────────────────


def test_validator_sockets_registered() -> None:
    comp = QuantityDtypeValidator()
    assert "findings" in comp.__haystack_input__._sockets_dict
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "warnings" in comp.__haystack_output__._sockets_dict


def test_validator_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("qty_dtype", QuantityDtypeValidator())
    assert "qty_dtype" in pipeline.graph.nodes
