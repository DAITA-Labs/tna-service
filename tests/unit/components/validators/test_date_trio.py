"""DateTrioValidator — chronological order check for per-PLI dates."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.components.validators.date_trio import DateTrioValidator


def _f(canonical: str, row: int, date: dt.date, col_letter: str = "D") -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col_letter, 2),
        value_coord=(col_letter, row),
        value=date, confidence=Confidence.HIGH, evidence=[],
    )


# ─── Happy path ───────────────────────────────────────────────────────────


def test_chronological_dates_yield_no_warnings() -> None:
    """ex_fty < shipment < delivery → no warnings."""
    findings = [
        _f("ex_fty_date",    3, dt.date(2026, 5, 1)),
        _f("shipment_date",  3, dt.date(2026, 5, 10)),
        _f("delivery_date",  3, dt.date(2026, 5, 20)),
    ]
    out = DateTrioValidator().run(findings=findings)
    assert out["warnings"] == []


def test_equal_dates_yield_no_warnings() -> None:
    """ex_fty == shipment == delivery → not an inversion, no warnings."""
    same = dt.date(2026, 5, 1)
    findings = [
        _f("ex_fty_date",    3, same),
        _f("shipment_date",  3, same),
        _f("delivery_date",  3, same),
    ]
    out = DateTrioValidator().run(findings=findings)
    assert out["warnings"] == []


# ─── Inversion cases ──────────────────────────────────────────────────────


def test_ex_fty_after_shipment_emits_warning() -> None:
    findings = [
        _f("ex_fty_date",   3, dt.date(2026, 5, 15)),
        _f("shipment_date", 3, dt.date(2026, 5, 10)),
    ]
    out = DateTrioValidator().run(findings=findings)
    assert len(out["warnings"]) == 1
    w = out["warnings"][0]
    assert w.name == "date_trio_inversion"
    assert w.severity == "warning"
    assert "ex_fty_date" in w.message
    assert "shipment_date" in w.message
    assert "row 3" in w.message


def test_shipment_after_delivery_emits_warning() -> None:
    findings = [
        _f("shipment_date", 3, dt.date(2026, 5, 20)),
        _f("delivery_date", 3, dt.date(2026, 5, 15)),
    ]
    out = DateTrioValidator().run(findings=findings)
    assert len(out["warnings"]) == 1
    assert "shipment_date" in out["warnings"][0].message


def test_all_three_inverted_emits_two_warnings() -> None:
    """Only adjacent comparisons emit — transitivity covers the third."""
    findings = [
        _f("ex_fty_date",   3, dt.date(2026, 5, 30)),
        _f("shipment_date", 3, dt.date(2026, 5, 20)),
        _f("delivery_date", 3, dt.date(2026, 5, 10)),
    ]
    out = DateTrioValidator().run(findings=findings)
    assert len(out["warnings"]) == 2
    pairs = {tuple(sorted(f.canonical for f in w.affects_findings))
             for w in out["warnings"]}
    assert pairs == {
        ("ex_fty_date", "shipment_date"),
        ("delivery_date", "shipment_date"),
    }


# ─── Multi-row scenarios ──────────────────────────────────────────────────


def test_warnings_emitted_per_offending_row_only() -> None:
    """Two PLI rows; one valid, one inverted — single warning for the inverted row."""
    findings = [
        # row 3 — valid
        _f("ex_fty_date",   3, dt.date(2026, 5, 1)),
        _f("shipment_date", 3, dt.date(2026, 5, 5)),
        _f("delivery_date", 3, dt.date(2026, 5, 10)),
        # row 4 — inverted
        _f("ex_fty_date",   4, dt.date(2026, 6, 10)),
        _f("shipment_date", 4, dt.date(2026, 6, 5)),
    ]
    out = DateTrioValidator().run(findings=findings)
    assert len(out["warnings"]) == 1
    assert "row 4" in out["warnings"][0].message


def test_warnings_sorted_by_row() -> None:
    """When multiple rows are inverted, output is in ascending row order."""
    findings = [
        _f("ex_fty_date",   7, dt.date(2026, 6, 10)),
        _f("shipment_date", 7, dt.date(2026, 6, 5)),
        _f("ex_fty_date",   3, dt.date(2026, 5, 10)),
        _f("shipment_date", 3, dt.date(2026, 5, 5)),
    ]
    out = DateTrioValidator().run(findings=findings)
    rows = [int(w.message.split("row ")[1].split(":")[0]) for w in out["warnings"]]
    assert rows == sorted(rows)


# ─── Partial data ─────────────────────────────────────────────────────────


def test_missing_date_pair_member_skips_check() -> None:
    """A PLI with only one date → no comparison can be made, no warning."""
    findings = [_f("ex_fty_date", 3, dt.date(2026, 5, 10))]
    out = DateTrioValidator().run(findings=findings)
    assert out["warnings"] == []


def test_only_ex_fty_and_delivery_not_checked() -> None:
    """The validator only checks adjacent pairs — ex_fty vs delivery alone doesn't trigger."""
    findings = [
        _f("ex_fty_date",   3, dt.date(2026, 5, 30)),
        _f("delivery_date", 3, dt.date(2026, 5, 10)),
        # no shipment_date → ex_fty and delivery don't get compared directly
    ]
    out = DateTrioValidator().run(findings=findings)
    assert out["warnings"] == []


# ─── Non-trio canonicals ignored ─────────────────────────────────────────


def test_non_trio_canonicals_ignored() -> None:
    findings = [
        _f("ex_fty_date",      3, dt.date(2026, 5, 10)),
        _f("shipment_date",    3, dt.date(2026, 5, 20)),
        Finding(canonical="io_number", label_coord=("A", 2),
                value_coord=("A", 3), value="IO-1",
                confidence=Confidence.HIGH, evidence=[]),
    ]
    out = DateTrioValidator().run(findings=findings)
    assert out["warnings"] == []


# ─── Component plumbing ──────────────────────────────────────────────────


def test_validator_sockets_registered() -> None:
    comp = DateTrioValidator()
    assert "findings" in comp.__haystack_input__._sockets_dict
    assert "warnings" in comp.__haystack_output__._sockets_dict


def test_validator_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("date_trio", DateTrioValidator())
    assert "date_trio" in pipeline.graph.nodes
