"""RowAlignmentValidator — majority-coverage non-mandatory canonical check."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.components.validators.row_alignment import RowAlignmentValidator
from tests.unit.components.field._bundles import make_bundle


def _bundle_with_rows(n_data_rows: int):
    """Build a bundle whose data_row_ranges cover rows 3..(2+n_data_rows)."""
    values = [[None] * 3 for _ in range(2 + n_data_rows)]
    return make_bundle(values, "io_number", columns={}, rows={})


def _f(canonical: str, row: int, value: object = "v") -> Finding:
    return Finding(
        canonical=canonical, label_coord=("A", 2),
        value_coord=("A", row), value=value,
        confidence=Confidence.HIGH, evidence=[],
    )


# ─── Happy paths ──────────────────────────────────────────────────────────


def test_full_coverage_no_warnings() -> None:
    """A canonical present on every PLI row → no gap warnings."""
    bundle = _bundle_with_rows(5)   # rows 3..7
    findings = [_f("style_code", r) for r in range(3, 8)]
    assert RowAlignmentValidator().run(findings=findings, bundle=bundle)["warnings"] == []


def test_low_coverage_treated_as_sparse() -> None:
    """≤70% coverage → column is legitimately sparse, no warnings."""
    bundle = _bundle_with_rows(10)   # rows 3..12
    findings = [_f("style_code", r) for r in (3, 4, 5)]   # 30% coverage
    assert RowAlignmentValidator().run(findings=findings, bundle=bundle)["warnings"] == []


def test_no_findings_no_warnings() -> None:
    bundle = _bundle_with_rows(5)
    assert RowAlignmentValidator().run(findings=[], bundle=bundle)["warnings"] == []


# ─── Gap detection ────────────────────────────────────────────────────────


def test_above_threshold_emits_gap_per_missing_row() -> None:
    """80% coverage → flag the 20% missing as gaps."""
    bundle = _bundle_with_rows(10)   # rows 3..12
    findings = [_f("style_code", r) for r in (3, 4, 5, 6, 7, 8, 9, 10)]   # 8/10 = 80%
    out = RowAlignmentValidator().run(findings=findings, bundle=bundle)
    gaps = [w for w in out["warnings"] if w.name == "row_alignment_gap"]
    assert len(gaps) == 2
    assert all(w.severity == "warning" for w in gaps)
    rows = sorted(int(w.message.split("row ")[1].split(" ")[0]) for w in gaps)
    assert rows == [11, 12]


def test_gap_warning_carries_canonical_and_coverage() -> None:
    bundle = _bundle_with_rows(10)
    findings = [_f("color_code", r) for r in range(3, 11)]   # rows 3..10 = 8/10 = 80%
    out = RowAlignmentValidator().run(findings=findings, bundle=bundle)
    gap = next(w for w in out["warnings"] if w.name == "row_alignment_gap")
    assert "color_code" in gap.message
    assert "8/10" in gap.message
    assert "80%" in gap.message


def test_threshold_boundary_70pct_exactly_no_warnings() -> None:
    """Exactly 70% sits on the boundary — no warnings (sparse interpretation)."""
    bundle = _bundle_with_rows(10)
    findings = [_f("style_code", r) for r in range(3, 10)]   # 7/10 = 70%
    out = RowAlignmentValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if w.name == "row_alignment_gap"] == []


def test_just_above_threshold_emits_warnings() -> None:
    bundle = _bundle_with_rows(13)   # 13 rows
    findings = [_f("style_code", r) for r in range(3, 13)]   # 10/13 ≈ 77%
    out = RowAlignmentValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if w.name == "row_alignment_gap"]


# ─── Mandatory canonicals ignored ────────────────────────────────────────


def test_mandatory_canonicals_skipped() -> None:
    """CardinalityValidator owns io_number / quantity gaps; we skip them."""
    bundle = _bundle_with_rows(10)
    findings = [_f("io_number", r) for r in range(3, 11)]   # 8/10 — would warn if non-mandatory
    out = RowAlignmentValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if "io_number" in w.message] == []


def test_quantity_canonical_skipped() -> None:
    bundle = _bundle_with_rows(10)
    findings = [_f("quantity", r, value=100) for r in range(3, 11)]
    out = RowAlignmentValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if "quantity" in w.message] == []


# ─── Multi-canonical scenarios ────────────────────────────────────────────


def test_multiple_canonicals_each_evaluated_independently() -> None:
    """One canonical full, one with gaps, one sparse → only the gap-canonical warns."""
    bundle = _bundle_with_rows(10)
    findings = (
        [_f("style_code", r) for r in range(3, 13)]              # full coverage
      + [_f("color_code", r) for r in range(3, 11)]              # 80% → warns
      + [_f("fabric_code", r) for r in (3, 4)]                   # 20% → sparse
    )
    out = RowAlignmentValidator().run(findings=findings, bundle=bundle)
    gaps = [w for w in out["warnings"] if w.name == "row_alignment_gap"]
    assert all("color_code" in w.message for w in gaps)
    assert len(gaps) == 2


def test_warnings_emitted_in_sorted_canonical_then_row_order() -> None:
    bundle = _bundle_with_rows(10)
    findings = (
        [_f("style_code", r) for r in (3, 4, 5, 6, 7, 8, 9, 10)]
      + [_f("color_code", r) for r in (3, 4, 5, 6, 7, 8, 9, 10)]
    )
    out = RowAlignmentValidator().run(findings=findings, bundle=bundle)
    gaps = [w for w in out["warnings"] if w.name == "row_alignment_gap"]
    # color_code (alphabetical) before style_code; rows within each in order
    canonicals = [w.message.split("`")[1] for w in gaps]
    assert canonicals == ["color_code"] * 2 + ["style_code"] * 2


# ─── Degenerate inputs ────────────────────────────────────────────────────


def test_findings_on_rows_outside_pli_set_ignored() -> None:
    """Findings claiming rows outside the data row range don't count toward coverage."""
    bundle = _bundle_with_rows(5)   # rows 3..7
    findings = (
        [_f("style_code", r) for r in (3, 4, 5)]      # 3/5 = 60% of PLI
      + [_f("style_code", 99)]                         # extraneous — ignored
    )
    out = RowAlignmentValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if w.name == "row_alignment_gap"] == []


def test_empty_bundle_no_warnings() -> None:
    bundle = _bundle_with_rows(0)
    bundle.hint.data_row_ranges.clear()
    findings = [_f("style_code", 3)]
    assert RowAlignmentValidator().run(findings=findings, bundle=bundle)["warnings"] == []


# ─── Component plumbing ──────────────────────────────────────────────────


def test_validator_sockets_registered() -> None:
    comp = RowAlignmentValidator()
    assert "findings" in comp.__haystack_input__._sockets_dict
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "warnings" in comp.__haystack_output__._sockets_dict


def test_validator_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("row_align", RowAlignmentValidator())
    assert "row_align" in pipeline.graph.nodes
