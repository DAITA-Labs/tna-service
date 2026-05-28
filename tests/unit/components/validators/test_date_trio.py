"""DateTrioValidator — chronological order + at-least-one presence."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.components.validators.date_trio import DateTrioValidator
from tests.unit.components.field._bundles import make_bundle


def _bundle_with_rows(n_data_rows: int):
    """Build a bundle whose data_row_ranges cover rows 3..(2+n_data_rows)."""
    values = [[None] * 3 for _ in range(2 + n_data_rows)]
    return make_bundle(values, "io_number", columns={}, rows={})


def _f(canonical: str, row: int, date: dt.date, col_letter: str = "D") -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col_letter, 2),
        value_coord=(col_letter, row),
        value=date, confidence=Confidence.HIGH, evidence=[],
    )


# ─── Chronological order (all three present) ───────────────────────────────


def test_chronological_dates_yield_no_warnings() -> None:
    """ex_fty < shipment < delivery → no warnings."""
    bundle = _bundle_with_rows(1)   # row 3
    findings = [
        _f("ex_fty_date",    3, dt.date(2026, 5, 1)),
        _f("shipment_date",  3, dt.date(2026, 5, 10)),
        _f("delivery_date",  3, dt.date(2026, 5, 20)),
    ]
    assert DateTrioValidator().run(findings=findings, bundle=bundle)["warnings"] == []


def test_equal_dates_yield_no_warnings() -> None:
    bundle = _bundle_with_rows(1)
    same = dt.date(2026, 5, 1)
    findings = [
        _f("ex_fty_date",    3, same),
        _f("shipment_date",  3, same),
        _f("delivery_date",  3, same),
    ]
    assert DateTrioValidator().run(findings=findings, bundle=bundle)["warnings"] == []


def test_ex_fty_after_shipment_emits_inversion_warning() -> None:
    bundle = _bundle_with_rows(1)
    findings = [
        _f("ex_fty_date",   3, dt.date(2026, 5, 15)),
        _f("shipment_date", 3, dt.date(2026, 5, 10)),
    ]
    warnings = DateTrioValidator().run(findings=findings, bundle=bundle)["warnings"]
    assert len(warnings) == 1
    assert warnings[0].name == "date_trio_inversion"
    assert warnings[0].severity == "warning"
    assert "ex_fty_date" in warnings[0].message


def test_shipment_after_delivery_emits_inversion_warning() -> None:
    bundle = _bundle_with_rows(1)
    findings = [
        _f("shipment_date", 3, dt.date(2026, 5, 20)),
        _f("delivery_date", 3, dt.date(2026, 5, 15)),
    ]
    warnings = DateTrioValidator().run(findings=findings, bundle=bundle)["warnings"]
    assert len(warnings) == 1
    assert "shipment_date" in warnings[0].message


def test_all_three_inverted_emits_two_inversion_warnings() -> None:
    """All three present + reversed order → 2 adjacent-pair warnings (transitivity
    covers the third)."""
    bundle = _bundle_with_rows(1)
    findings = [
        _f("ex_fty_date",   3, dt.date(2026, 5, 30)),
        _f("shipment_date", 3, dt.date(2026, 5, 20)),
        _f("delivery_date", 3, dt.date(2026, 5, 10)),
    ]
    out = DateTrioValidator().run(findings=findings, bundle=bundle)
    inversions = [w for w in out["warnings"] if w.name == "date_trio_inversion"]
    assert len(inversions) == 2


# ─── Missing-middle case (the new fix) ────────────────────────────────────


def test_ex_fty_after_delivery_when_shipment_missing_emits_warning() -> None:
    """When shipment is missing, ex_fty and delivery are compared directly."""
    bundle = _bundle_with_rows(1)
    findings = [
        _f("ex_fty_date",   3, dt.date(2026, 5, 30)),
        _f("delivery_date", 3, dt.date(2026, 5, 10)),
    ]
    out = DateTrioValidator().run(findings=findings, bundle=bundle)
    inversions = [w for w in out["warnings"] if w.name == "date_trio_inversion"]
    assert len(inversions) == 1
    msg = inversions[0].message
    assert "ex_fty_date" in msg
    assert "delivery_date" in msg


def test_ex_fty_before_delivery_when_shipment_missing_no_inversion() -> None:
    bundle = _bundle_with_rows(1)
    findings = [
        _f("ex_fty_date",   3, dt.date(2026, 5, 1)),
        _f("delivery_date", 3, dt.date(2026, 5, 30)),
    ]
    out = DateTrioValidator().run(findings=findings, bundle=bundle)
    inversions = [w for w in out["warnings"] if w.name == "date_trio_inversion"]
    assert inversions == []


# ─── At-least-one presence ────────────────────────────────────────────────


def test_pli_with_no_dates_emits_missing_date_trio_error() -> None:
    """A PLI row with none of the three dates → error-level warning."""
    bundle = _bundle_with_rows(1)
    out = DateTrioValidator().run(findings=[], bundle=bundle)
    missing = [w for w in out["warnings"] if w.name == "missing_date_trio"]
    assert len(missing) == 1
    w = missing[0]
    assert w.severity == "error"
    assert "row 3" in w.message


def test_pli_with_just_one_date_satisfies_presence_check() -> None:
    """Any single date satisfies the at-least-one requirement."""
    bundle = _bundle_with_rows(1)
    findings = [_f("ex_fty_date", 3, dt.date(2026, 5, 1))]
    out = DateTrioValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if w.name == "missing_date_trio"] == []


def test_multiple_rows_some_missing_dates() -> None:
    """Two PLIs: one with dates, one without → one missing_date_trio error."""
    bundle = _bundle_with_rows(2)   # rows 3, 4
    findings = [_f("delivery_date", 3, dt.date(2026, 5, 1))]
    out = DateTrioValidator().run(findings=findings, bundle=bundle)
    missing = [w for w in out["warnings"] if w.name == "missing_date_trio"]
    assert len(missing) == 1
    assert "row 4" in missing[0].message


# ─── Multi-row inversion behaviour ────────────────────────────────────────


def test_warnings_emitted_only_on_offending_rows() -> None:
    bundle = _bundle_with_rows(2)
    findings = [
        # row 3 — valid
        _f("ex_fty_date",   3, dt.date(2026, 5, 1)),
        _f("shipment_date", 3, dt.date(2026, 5, 5)),
        _f("delivery_date", 3, dt.date(2026, 5, 10)),
        # row 4 — inverted
        _f("ex_fty_date",   4, dt.date(2026, 6, 10)),
        _f("shipment_date", 4, dt.date(2026, 6, 5)),
    ]
    out = DateTrioValidator().run(findings=findings, bundle=bundle)
    inversions = [w for w in out["warnings"] if w.name == "date_trio_inversion"]
    assert len(inversions) == 1
    assert "row 4" in inversions[0].message


# ─── Non-trio canonicals ignored ──────────────────────────────────────────


def test_non_trio_canonicals_ignored() -> None:
    bundle = _bundle_with_rows(1)
    findings = [
        _f("ex_fty_date",      3, dt.date(2026, 5, 10)),
        _f("shipment_date",    3, dt.date(2026, 5, 20)),
        Finding(canonical="io_number", label_coord=("A", 2),
                value_coord=("A", 3), value="IO-1",
                confidence=Confidence.HIGH, evidence=[]),
    ]
    out = DateTrioValidator().run(findings=findings, bundle=bundle)
    inversions = [w for w in out["warnings"] if w.name == "date_trio_inversion"]
    assert inversions == []


# ─── Component plumbing ──────────────────────────────────────────────────


def test_validator_sockets_registered() -> None:
    comp = DateTrioValidator()
    assert "findings" in comp.__haystack_input__._sockets_dict
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "warnings" in comp.__haystack_output__._sockets_dict


def test_validator_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("date_trio", DateTrioValidator())
    assert "date_trio" in pipeline.graph.nodes
