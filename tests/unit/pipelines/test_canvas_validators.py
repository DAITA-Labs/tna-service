"""Tests for the canvas-architecture validators pipeline factory."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.artifacts.structure import (
    Rect,
    StageArena,
    StageBand,
)
from app.pipelines.canvas_validators import (
    CanvasWarningAggregator,
    make_canvas_validators_pipeline,
)
from app.specs.schemas import FinalStage
from tests.unit.components.field._bundles import make_bundle


# ─── Fixtures ────────────────────────────────────────────────────────────


def _bundle(n_data_rows: int = 3, n_cols: int = 8,
            stage_arenas=None, stage_bands=None):
    """Build a bundle with `n_data_rows` PLI rows starting at row 3."""
    values = [[None] * n_cols for _ in range(2 + n_data_rows)]
    return make_bundle(
        values, "io_number", columns={}, rows={},
        stage_arenas=stage_arenas,
        stage_bands=stage_bands,
    )


def _f(canonical: str, col: str, row: int, value: object = "v") -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col, 2),
        value_coord=(col, row), value=value,
        confidence=Confidence.HIGH, evidence=[],
    )


def _run(pipeline: Pipeline, findings, bundle, stages_per_row=None):
    """Drive the pipeline by setting every validator's inputs."""
    stages = stages_per_row or {}
    return pipeline.run({
        "cardinality":     {"findings": findings, "bundle": bundle},
        "row_alignment":   {"findings": findings, "bundle": bundle},
        "date_trio":       {"findings": findings, "bundle": bundle},
        "stage_wins":      {"findings": findings, "bundle": bundle},
        "stage_structure": {"bundle": bundle},
        "quantity_dtype":  {"findings": findings, "bundle": bundle},
        "stage_sequence":  {"stages_per_row": stages},
    })


# ─── Factory shape ───────────────────────────────────────────────────────


def test_factory_returns_pipeline_with_eight_components() -> None:
    """Seven validators plus the aggregator."""
    pipeline = make_canvas_validators_pipeline()
    assert isinstance(pipeline, Pipeline)
    expected = {
        "cardinality", "row_alignment", "date_trio", "stage_wins",
        "stage_structure", "quantity_dtype", "stage_sequence", "aggregator",
    }
    assert set(pipeline.graph.nodes) == expected


def test_every_validator_connects_to_aggregator() -> None:
    """Each validator's `warnings` output feeds one aggregator socket."""
    pipeline = make_canvas_validators_pipeline()
    edge_pairs = {(u, v) for (u, v, _key) in pipeline.graph.edges}
    for validator in ("cardinality", "row_alignment", "date_trio", "stage_wins",
                      "stage_structure", "quantity_dtype", "stage_sequence"):
        assert (validator, "aggregator") in edge_pairs, f"{validator} → aggregator missing"


def test_factory_is_idempotent() -> None:
    """Each invocation returns a fresh pipeline (no shared mutable state)."""
    p1 = make_canvas_validators_pipeline()
    p2 = make_canvas_validators_pipeline()
    assert p1 is not p2
    assert set(p1.graph.nodes) == set(p2.graph.nodes)


# ─── End-to-end runs ─────────────────────────────────────────────────────


def test_empty_inputs_yield_no_warnings() -> None:
    pipeline = make_canvas_validators_pipeline()
    bundle = make_bundle([[None]], "io_number", columns={}, rows={})
    bundle.hint.data_row_ranges.clear()
    result = _run(pipeline, findings=[], bundle=bundle)
    assert result["aggregator"]["warnings"] == []


def test_cardinality_warning_surfaces() -> None:
    pipeline = make_canvas_validators_pipeline()
    bundle = _bundle(n_data_rows=1)
    result = _run(pipeline, findings=[], bundle=bundle)
    names = [w.name for w in result["aggregator"]["warnings"]]
    assert any(n.startswith("missing_mandatory_") for n in names)


def test_date_trio_warning_surfaces() -> None:
    pipeline = make_canvas_validators_pipeline()
    bundle = _bundle(n_data_rows=1)
    findings = [
        _f("io_number", "A", 3),
        _f("quantity",  "B", 3, value=100),
        _f("ex_fty_date",   "C", 3, value=dt.date(2026, 5, 30)),
        _f("delivery_date", "D", 3, value=dt.date(2026, 5, 10)),
    ]
    result = _run(pipeline, findings=findings, bundle=bundle)
    assert any(w.name == "date_trio_inversion"
               for w in result["aggregator"]["warnings"])


def test_stage_wins_warning_surfaces() -> None:
    pipeline = make_canvas_validators_pipeline()
    bundle = _bundle(n_data_rows=1, stage_arenas=[StageArena(rect=Rect(3, 4, 10, 6))])
    findings = [
        _f("io_number", "A", 3),
        _f("quantity",  "B", 3, value=100),
        _f("delivery_date", "E", 3, value=dt.date(2026, 5, 1)),    # inside arena
    ]
    result = _run(pipeline, findings=findings, bundle=bundle)
    assert any(w.name == "stage_wins_over_date_identifier"
               for w in result["aggregator"]["warnings"])


def test_stage_structure_warning_surfaces() -> None:
    pipeline = make_canvas_validators_pipeline()
    bands = [
        StageBand(rect=Rect(r0=4, c0=2, r1=6, c1=4), name_coord=("B", 3), name_text="Fabric"),
        StageBand(rect=Rect(r0=5, c0=5, r1=7, c1=7), name_coord=("E", 4), name_text="Cutting"),
    ]
    bundle = _bundle(n_data_rows=5, stage_bands=bands)
    findings = [_f("io_number", "A", 3), _f("quantity", "H", 3, value=100)]
    result = _run(pipeline, findings=findings, bundle=bundle)
    assert any(w.name == "stage_band_anchor_row_misaligned"
               for w in result["aggregator"]["warnings"])


def test_row_alignment_warning_surfaces() -> None:
    pipeline = make_canvas_validators_pipeline()
    bundle = _bundle(n_data_rows=5)
    findings = (
        [_f("io_number",  "A", r) for r in range(3, 8)]
      + [_f("quantity",   "B", r, value=100) for r in range(3, 8)]
      + [_f("style_code", "C", r) for r in (3, 4, 5, 6)]
      + [_f("ex_fty_date","D", r, value=dt.date(2026,5,1)) for r in range(3, 8)]
    )
    result = _run(pipeline, findings=findings, bundle=bundle)
    assert any(w.name == "row_alignment_gap"
               for w in result["aggregator"]["warnings"])


def test_quantity_dtype_warning_surfaces() -> None:
    pipeline = make_canvas_validators_pipeline()
    values = [[None] * 3 for _ in range(2)]
    for v in ("X", "X", "X", "X", "X", "X", "X", 100):
        values.append([None, v, None])
    bundle = make_bundle(values, "quantity", columns={"quantity": [2]}, rows={})
    findings = [_f("quantity", "B", r) for r in range(3, 11)]
    result = _run(pipeline, findings=findings, bundle=bundle)
    assert any(w.name == "quantity_column_low_numeric_density"
               for w in result["aggregator"]["warnings"])


def test_stage_sequence_warning_surfaces() -> None:
    pipeline = make_canvas_validators_pipeline()
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
    result = _run(pipeline, findings=findings, bundle=bundle, stages_per_row=stages)
    assert any(w.name == "stage_sequence_inversion"
               for w in result["aggregator"]["warnings"])


# ─── Ordering & determinism ──────────────────────────────────────────────


def test_warning_order_follows_aggregator_socket_order() -> None:
    """row_alignment comes before date_trio in the concatenated output."""
    pipeline = make_canvas_validators_pipeline()
    bundle = _bundle(n_data_rows=5)
    findings = (
        [_f("io_number", "A", r) for r in range(3, 8)]
      + [_f("quantity",  "B", r, value=100) for r in range(3, 8)]
      + [_f("style_code", "C", r) for r in (3, 4, 5, 6)]
      + [_f("ex_fty_date",   "D", 3, value=dt.date(2026, 5, 30))]
      + [_f("delivery_date", "E", 3, value=dt.date(2026, 5, 10))]
    )
    warnings = _run(pipeline, findings=findings, bundle=bundle)["aggregator"]["warnings"]
    names = [w.name for w in warnings]
    row_align_idx = next(i for i, n in enumerate(names) if n == "row_alignment_gap")
    date_trio_idx = next(i for i, n in enumerate(names) if n == "date_trio_inversion")
    assert row_align_idx < date_trio_idx


def test_repeated_runs_produce_same_ordering() -> None:
    pipeline = make_canvas_validators_pipeline()
    bundle = _bundle(n_data_rows=2)
    findings = [_f("ex_fty_date",   "D", 3, value=dt.date(2026, 5, 30)),
                _f("delivery_date", "E", 3, value=dt.date(2026, 5, 10)),
                _f("io_number", "A", 3), _f("quantity", "B", 3, value=100),
                _f("io_number", "A", 4), _f("quantity", "B", 4, value=100)]
    r1 = _run(pipeline, findings=findings, bundle=bundle)["aggregator"]["warnings"]
    r2 = _run(pipeline, findings=findings, bundle=bundle)["aggregator"]["warnings"]
    assert [w.name for w in r1] == [w.name for w in r2]


# ─── Aggregator unit-level ────────────────────────────────────────────────


def test_aggregator_sockets_registered() -> None:
    comp = CanvasWarningAggregator()
    inputs = comp.__haystack_input__._sockets_dict
    for socket in ("cardinality_warnings", "row_alignment_warnings",
                   "date_trio_warnings", "stage_wins_warnings",
                   "stage_structure_warnings", "quantity_dtype_warnings",
                   "stage_sequence_warnings"):
        assert socket in inputs, f"missing aggregator input socket {socket}"
    assert "warnings" in comp.__haystack_output__._sockets_dict


def test_aggregator_concatenates_in_socket_declaration_order() -> None:
    from app.artifacts.finding import ValidationWarning
    def w(n: str) -> ValidationWarning:
        return ValidationWarning(name=n, severity="info", message=n)

    out = CanvasWarningAggregator().run(
        cardinality_warnings=[w("c")],
        row_alignment_warnings=[w("r")],
        date_trio_warnings=[w("d")],
        stage_wins_warnings=[w("sw")],
        stage_structure_warnings=[w("ss")],
        quantity_dtype_warnings=[w("q")],
        stage_sequence_warnings=[w("ssq")],
    )
    assert [x.name for x in out["warnings"]] == ["c", "r", "d", "sw", "ss", "q", "ssq"]
