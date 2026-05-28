"""CardinalityValidator — mandatory-canonical coverage check."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.components.validators.cardinality import CardinalityValidator
from tests.unit.components.field._bundles import make_bundle


def _bundle_with_rows(n_data_rows: int):
    """Build a bundle whose data_row_ranges cover rows 3..(2+n_data_rows)."""
    values = [[None] * 3 for _ in range(2 + n_data_rows)]
    return make_bundle(values, "io_number", columns={}, rows={})


def _f(canonical: str, row: int, col_letter: str = "A") -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col_letter, 2),
        value_coord=(col_letter, row),
        value="x", confidence=Confidence.HIGH, evidence=[],
    )


# ─── Happy path ───────────────────────────────────────────────────────────


def test_all_mandatory_canonicals_present_yields_no_warnings() -> None:
    """Every PLI row has both io_number and quantity → no warnings."""
    bundle = _bundle_with_rows(3)   # rows 3, 4, 5
    findings = [
        _f("io_number", 3), _f("quantity", 3, "B"),
        _f("io_number", 4), _f("quantity", 4, "B"),
        _f("io_number", 5), _f("quantity", 5, "B"),
    ]
    out = CardinalityValidator().run(findings=findings, bundle=bundle)
    assert out["warnings"] == []


# ─── Missing mandatory canonicals ─────────────────────────────────────────


def test_missing_io_number_in_one_row_emits_one_warning() -> None:
    bundle = _bundle_with_rows(3)
    findings = [
        _f("io_number", 3), _f("quantity", 3, "B"),
        # row 4 missing io_number
        _f("quantity", 4, "B"),
        _f("io_number", 5), _f("quantity", 5, "B"),
    ]
    out = CardinalityValidator().run(findings=findings, bundle=bundle)
    assert len(out["warnings"]) == 1
    w = out["warnings"][0]
    assert w.name == "missing_mandatory_io_number"
    assert w.severity == "error"
    assert "row 4" in w.message
    assert "io_number" in w.message


def test_missing_quantity_in_two_rows_emits_two_warnings() -> None:
    bundle = _bundle_with_rows(3)
    findings = [
        _f("io_number", 3),                       # row 3 missing quantity
        _f("io_number", 4), _f("quantity", 4, "B"),
        _f("io_number", 5),                       # row 5 missing quantity
    ]
    out = CardinalityValidator().run(findings=findings, bundle=bundle)
    names = [w.name for w in out["warnings"]]
    rows = [int(w.message.split("row ")[1].split(" ")[0]) for w in out["warnings"]]
    assert names == ["missing_mandatory_quantity"] * 2
    assert sorted(rows) == [3, 5]


def test_row_missing_both_mandatories_emits_two_warnings() -> None:
    bundle = _bundle_with_rows(2)   # rows 3, 4
    findings = [
        _f("io_number", 3), _f("quantity", 3, "B"),
        # row 4 missing both
    ]
    out = CardinalityValidator().run(findings=findings, bundle=bundle)
    names = sorted(w.name for w in out["warnings"])
    assert names == ["missing_mandatory_io_number", "missing_mandatory_quantity"]


# ─── Non-mandatory canonicals don't affect validation ─────────────────────


def test_optional_canonicals_not_required_per_row() -> None:
    """Style/color/fabric/etc. are optional — their absence doesn't trigger warnings."""
    bundle = _bundle_with_rows(2)
    findings = [
        _f("io_number", 3), _f("quantity", 3, "B"),
        _f("io_number", 4), _f("quantity", 4, "B"),
        # no style_code / color_code / etc. findings — but those aren't mandatory
    ]
    out = CardinalityValidator().run(findings=findings, bundle=bundle)
    assert out["warnings"] == []


# ─── Empty / degenerate inputs ────────────────────────────────────────────


def test_no_pli_rows_yields_no_warnings() -> None:
    """A sheet with no data_row_ranges → nothing to validate, no warnings."""
    bundle = _bundle_with_rows(2)
    bundle.hint.data_row_ranges = []
    out = CardinalityValidator().run(findings=[], bundle=bundle)
    assert out["warnings"] == []


def test_no_findings_at_all_emits_warning_per_mandatory_canonical_per_row() -> None:
    """Three PLI rows × two mandatory canonicals → six warnings."""
    bundle = _bundle_with_rows(3)
    out = CardinalityValidator().run(findings=[], bundle=bundle)
    assert len(out["warnings"]) == 6


# ─── Component plumbing ──────────────────────────────────────────────────


def test_validator_sockets_registered() -> None:
    comp = CardinalityValidator()
    assert "findings" in comp.__haystack_input__._sockets_dict
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "warnings" in comp.__haystack_output__._sockets_dict


def test_validator_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("cardinality", CardinalityValidator())
    assert "cardinality" in pipeline.graph.nodes
