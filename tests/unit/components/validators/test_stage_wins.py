"""StageWinsValidator — date identifier findings must not sit in a StageArena."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.artifacts.structure import Rect, StageArena
from app.components.validators.stage_wins import StageWinsValidator
from tests.unit.components.field._bundles import make_bundle


def _bundle(arenas: list[StageArena] | None = None, n_rows: int = 10, n_cols: int = 8):
    values = [[None] * n_cols for _ in range(n_rows)]
    return make_bundle(
        values, "io_number", columns={}, rows={},
        stage_arenas=arenas,
    )


def _f(canonical: str, col: str, row: int) -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col, 2),
        value_coord=(col, row), value=dt.date(2026, 5, 1),
        confidence=Confidence.HIGH, evidence=[],
    )


# ─── No-arena baseline ────────────────────────────────────────────────────


def test_no_stage_arenas_no_warnings() -> None:
    """When the structure phase emitted no arenas, every date finding passes."""
    findings = [_f("delivery_date", "D", 3), _f("shipment_date", "E", 4)]
    assert StageWinsValidator().run(findings=findings, bundle=_bundle())["warnings"] == []


def test_no_date_findings_no_warnings() -> None:
    arenas = [StageArena(rect=Rect(3, 4, 10, 6))]
    assert StageWinsValidator().run(findings=[], bundle=_bundle(arenas))["warnings"] == []


# ─── Containment behaviour ────────────────────────────────────────────────


def test_date_inside_arena_emits_warning() -> None:
    arenas = [StageArena(rect=Rect(3, 4, 10, 6))]   # rows 3..10, cols D..F
    findings = [_f("delivery_date", "E", 5)]
    out = StageWinsValidator().run(findings=findings, bundle=_bundle(arenas))
    assert len(out["warnings"]) == 1
    w = out["warnings"][0]
    assert w.name == "stage_wins_over_date_identifier"
    assert w.severity == "warning"
    assert "delivery_date" in w.message
    assert "E5" in w.message
    assert w.affects_findings == findings


def test_date_outside_arena_no_warning() -> None:
    arenas = [StageArena(rect=Rect(3, 4, 10, 6))]
    findings = [_f("delivery_date", "B", 5)]    # col B, outside cols D..F
    assert StageWinsValidator().run(findings=findings, bundle=_bundle(arenas))["warnings"] == []


def test_date_on_arena_top_left_corner_emits_warning() -> None:
    """Inclusive containment — the (r0, c0) corner counts as inside."""
    arenas = [StageArena(rect=Rect(3, 4, 10, 6))]
    findings = [_f("ex_fty_date", "D", 3)]
    assert StageWinsValidator().run(findings=findings, bundle=_bundle(arenas))["warnings"]


def test_date_on_arena_bottom_right_corner_emits_warning() -> None:
    arenas = [StageArena(rect=Rect(3, 4, 10, 6))]
    findings = [_f("shipment_date", "F", 10)]
    assert StageWinsValidator().run(findings=findings, bundle=_bundle(arenas))["warnings"]


def test_date_one_row_above_arena_no_warning() -> None:
    arenas = [StageArena(rect=Rect(3, 4, 10, 6))]
    findings = [_f("delivery_date", "E", 2)]
    assert StageWinsValidator().run(findings=findings, bundle=_bundle(arenas))["warnings"] == []


def test_date_one_col_right_of_arena_no_warning() -> None:
    arenas = [StageArena(rect=Rect(3, 4, 10, 6))]
    findings = [_f("delivery_date", "G", 5)]
    assert StageWinsValidator().run(findings=findings, bundle=_bundle(arenas))["warnings"] == []


# ─── Multi-arena scenarios ────────────────────────────────────────────────


def test_one_warning_per_finding_across_multiple_arenas() -> None:
    """A finding inside two overlapping arenas still produces one warning."""
    arenas = [
        StageArena(rect=Rect(3, 4, 10, 6)),
        StageArena(rect=Rect(3, 5, 10, 7)),    # overlaps at col E..F, rows 3..10
    ]
    findings = [_f("delivery_date", "E", 5)]
    out = StageWinsValidator().run(findings=findings, bundle=_bundle(arenas))
    assert len(out["warnings"]) == 1


def test_multiple_findings_each_evaluated() -> None:
    arenas = [StageArena(rect=Rect(3, 4, 10, 6))]
    findings = [
        _f("delivery_date", "E", 5),   # inside → warns
        _f("shipment_date", "B", 5),   # outside → ok
        _f("ex_fty_date",   "F", 7),   # inside → warns
    ]
    out = StageWinsValidator().run(findings=findings, bundle=_bundle(arenas))
    assert len(out["warnings"]) == 2
    canonicals = sorted({w.affects_findings[0].canonical for w in out["warnings"]})
    assert canonicals == ["delivery_date", "ex_fty_date"]


def test_finding_inside_one_of_many_arenas_emits_warning() -> None:
    arenas = [
        StageArena(rect=Rect(3, 1, 5, 2)),     # far-left band
        StageArena(rect=Rect(3, 8, 10, 10)),   # far-right band
        StageArena(rect=Rect(3, 4, 10, 6)),    # middle band
    ]
    findings = [_f("delivery_date", "E", 5)]   # middle hit
    assert StageWinsValidator().run(findings=findings, bundle=_bundle(arenas))["warnings"]


# ─── Non-date canonicals ignored ──────────────────────────────────────────


def test_non_date_canonicals_inside_arena_ignored() -> None:
    """The validator only cares about date identifiers, not other canonicals."""
    arenas = [StageArena(rect=Rect(3, 4, 10, 6))]
    findings = [
        Finding(canonical="io_number", label_coord=("E", 2),
                value_coord=("E", 5), value="IO-1",
                confidence=Confidence.HIGH, evidence=[]),
        Finding(canonical="style_code", label_coord=("E", 2),
                value_coord=("E", 6), value="S-1",
                confidence=Confidence.HIGH, evidence=[]),
    ]
    assert StageWinsValidator().run(findings=findings, bundle=_bundle(arenas))["warnings"] == []


# ─── Component plumbing ──────────────────────────────────────────────────


def test_validator_sockets_registered() -> None:
    comp = StageWinsValidator()
    assert "findings" in comp.__haystack_input__._sockets_dict
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "warnings" in comp.__haystack_output__._sockets_dict


def test_validator_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("stage_wins", StageWinsValidator())
    assert "stage_wins" in pipeline.graph.nodes
