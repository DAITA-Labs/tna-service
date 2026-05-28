"""CanvasValidatorOrchestrator — runs every canvas-arch validator in order."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.artifacts.structure import (
    MergeSpan,
    Rect,
    StageArena,
    StageBand,
)
from app.components.validators._orchestrator import CanvasValidatorOrchestrator
from app.specs.schemas import FinalStage
from tests.unit.components.field._bundles import make_bundle


# ─── Fixtures ────────────────────────────────────────────────────────────


def _bundle(n_data_rows: int = 3, n_cols: int = 8,
            stage_arenas=None, stage_bands=None, merge_spans=None):
    """Build a bundle with `n_data_rows` PLI rows starting at row 3."""
    values = [[None] * n_cols for _ in range(2 + n_data_rows)]
    return make_bundle(
        values, "io_number", columns={}, rows={},
        stage_arenas=stage_arenas,
        stage_bands=stage_bands,
        merge_spans=merge_spans,
    )


def _f(canonical: str, col: str, row: int, value: object = "v") -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col, 2),
        value_coord=(col, row), value=value,
        confidence=Confidence.HIGH, evidence=[],
    )


# ─── Empty-input path ────────────────────────────────────────────────────


def test_empty_inputs_yield_no_warnings() -> None:
    """No findings, no stages, an empty bundle — no validator finds anything."""
    bundle = make_bundle([[None]], "io_number", columns={}, rows={})
    bundle.hint.data_row_ranges.clear()
    out = CanvasValidatorOrchestrator().run(findings=[], bundle=bundle)
    assert out["warnings"] == []


def test_stages_per_row_default_is_empty() -> None:
    """Caller may omit stages_per_row — defaults to empty dict, no errors."""
    bundle = _bundle(n_data_rows=1)
    out = CanvasValidatorOrchestrator().run(findings=[_f("io_number", "A", 3),
                                                       _f("quantity",  "B", 3, value=100),
                                                       _f("ex_fty_date", "C", 3, value=dt.date(2026,5,1))],
                                              bundle=bundle)
    assert out["warnings"] == []


# ─── Per-validator triggers ──────────────────────────────────────────────


def test_cardinality_warning_surfaces() -> None:
    """A missing io_number on a PLI row triggers CardinalityValidator."""
    bundle = _bundle(n_data_rows=1)
    # No findings at all → io_number + quantity both missing on row 3
    out = CanvasValidatorOrchestrator().run(findings=[], bundle=bundle)
    names = [w.name for w in out["warnings"]]
    assert any(n.startswith("missing_mandatory_") for n in names)


def test_date_trio_warning_surfaces() -> None:
    bundle = _bundle(n_data_rows=1)
    findings = [
        _f("io_number", "A", 3),
        _f("quantity",  "B", 3, value=100),
        _f("ex_fty_date",   "C", 3, value=dt.date(2026, 5, 30)),
        _f("delivery_date", "D", 3, value=dt.date(2026, 5, 10)),
    ]
    out = CanvasValidatorOrchestrator().run(findings=findings, bundle=bundle)
    assert any(w.name == "date_trio_inversion" for w in out["warnings"])


def test_stage_wins_warning_surfaces() -> None:
    arenas = [StageArena(rect=Rect(3, 4, 10, 6))]
    bundle = _bundle(n_data_rows=1, stage_arenas=arenas)
    findings = [
        _f("io_number", "A", 3),
        _f("quantity",  "B", 3, value=100),
        _f("delivery_date", "E", 3, value=dt.date(2026, 5, 1)),     # inside arena
    ]
    out = CanvasValidatorOrchestrator().run(findings=findings, bundle=bundle)
    assert any(w.name == "stage_wins_over_date_identifier" for w in out["warnings"])


def test_stage_structure_warning_surfaces() -> None:
    """Two bands at different anchor rows → anchor row misalignment error."""
    bands = [
        StageBand(rect=Rect(r0=4, c0=2, r1=6, c1=4), name_coord=("B", 3), name_text="Fabric"),
        StageBand(rect=Rect(r0=5, c0=5, r1=7, c1=7), name_coord=("E", 4), name_text="Cutting"),
    ]
    bundle = _bundle(n_data_rows=5, stage_bands=bands)
    findings = [_f("io_number", "A", 3), _f("quantity", "H", 3, value=100)]
    out = CanvasValidatorOrchestrator().run(findings=findings, bundle=bundle)
    assert any(w.name == "stage_band_anchor_row_misaligned" for w in out["warnings"])


def test_row_alignment_warning_surfaces() -> None:
    """style_code at 4/5 of 5 rows → row alignment gap on the missing row."""
    bundle = _bundle(n_data_rows=5)
    findings = (
        [_f("io_number",  "A", r) for r in range(3, 8)]
      + [_f("quantity",   "B", r, value=100) for r in range(3, 8)]
      + [_f("style_code", "C", r) for r in (3, 4, 5, 6)]    # 4/5 = 80%
      + [_f("ex_fty_date","D", r, value=dt.date(2026,5,1)) for r in range(3, 8)]
    )
    out = CanvasValidatorOrchestrator().run(findings=findings, bundle=bundle)
    assert any(w.name == "row_alignment_gap" for w in out["warnings"])


def test_quantity_dtype_warning_surfaces() -> None:
    """Quantity column with mostly string cells fires the dtype warning."""
    values = [[None] * 3 for _ in range(2)]   # header rows
    for v in ("X", "X", "X", "X", "X", "X", "X", 100):
        values.append([None, v, None])
    bundle = make_bundle(values, "quantity", columns={"quantity": [2]}, rows={})
    findings = [_f("quantity", "B", r) for r in range(3, 11)]
    out = CanvasValidatorOrchestrator().run(findings=findings, bundle=bundle)
    assert any(w.name == "quantity_column_low_numeric_density" for w in out["warnings"])


def test_stage_sequence_warning_surfaces() -> None:
    """Inverted stages in stages_per_row produce a stage_sequence_inversion warning."""
    bundle = _bundle(n_data_rows=1)
    findings = [_f("io_number", "A", 3),
                _f("quantity",  "B", 3, value=100),
                _f("ex_fty_date", "C", 3, value=dt.date(2026, 5, 1))]
    stages = {
        3: [
            FinalStage(name="Fabric",           canonical="fabric",
                       plan_date=dt.date(2026, 6, 1), plan_date_col=4,
                       column_range=(4, 4), stage_metadata={}),
            FinalStage(name="Final Inspection", canonical="final_inspection",
                       plan_date=dt.date(2026, 5, 1), plan_date_col=5,
                       column_range=(5, 5), stage_metadata={}),
        ],
    }
    out = CanvasValidatorOrchestrator().run(findings=findings, bundle=bundle, stages_per_row=stages)
    assert any(w.name == "stage_sequence_inversion" for w in out["warnings"])


# ─── Ordering ────────────────────────────────────────────────────────────


def test_warning_order_follows_validator_chain() -> None:
    """Triggers from multiple validators appear in chain order: cardinality
    → row_alignment → date_trio → stage_wins → stage_structure → quantity_dtype
    → stage_sequence."""
    # 5 PLI rows. Style_code on 4/5 = 80% → row_alignment gap on row 7.
    # Row 3 also carries an inverted date pair (covers date_trio).
    bundle = _bundle(n_data_rows=5)
    findings = (
        [_f("io_number", "A", r) for r in range(3, 8)]
      + [_f("quantity",  "B", r, value=100) for r in range(3, 8)]
      + [_f("style_code", "C", r) for r in (3, 4, 5, 6)]
      + [_f("ex_fty_date",   "D", 3, value=dt.date(2026, 5, 30))]
      + [_f("delivery_date", "E", 3, value=dt.date(2026, 5, 10))]      # inversion
    )
    out = CanvasValidatorOrchestrator().run(findings=findings, bundle=bundle)

    seen_names = [w.name for w in out["warnings"]]
    row_alignment_idx = next(i for i, n in enumerate(seen_names) if n == "row_alignment_gap")
    date_trio_idx     = next(i for i, n in enumerate(seen_names) if n == "date_trio_inversion")
    assert row_alignment_idx < date_trio_idx


def test_repeated_calls_produce_same_ordering() -> None:
    """Determinism — running twice with the same input gives the same sequence."""
    bundle = _bundle(n_data_rows=2)
    findings = [_f("ex_fty_date",   "D", 3, value=dt.date(2026, 5, 30)),
                _f("delivery_date", "E", 3, value=dt.date(2026, 5, 10)),
                _f("io_number", "A", 3), _f("quantity", "B", 3, value=100),
                _f("io_number", "A", 4), _f("quantity", "B", 4, value=100)]
    orch = CanvasValidatorOrchestrator()
    out1 = orch.run(findings=findings, bundle=bundle)
    out2 = orch.run(findings=findings, bundle=bundle)
    assert [w.name for w in out1["warnings"]] == [w.name for w in out2["warnings"]]


# ─── Component plumbing ──────────────────────────────────────────────────


def test_orchestrator_sockets_registered() -> None:
    comp = CanvasValidatorOrchestrator()
    inputs = comp.__haystack_input__._sockets_dict
    assert "findings" in inputs
    assert "bundle" in inputs
    assert "stages_per_row" in inputs
    assert "warnings" in comp.__haystack_output__._sockets_dict


def test_orchestrator_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("validators", CanvasValidatorOrchestrator())
    assert "validators" in pipeline.graph.nodes
