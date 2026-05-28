"""Tests for the canvas-architecture judges pipeline factory."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding, ValidationWarning
from app.pipelines.canvas_judges import make_canvas_judges_pipeline
from app.specs.schemas import FinalStage, MetadataEntry
from tests.fixtures.fake_llm import FakeLLM
from tests.unit.components.field._bundles import make_bundle


def _bundle():
    return make_bundle([[None] * 5 for _ in range(8)], "io_number", columns={}, rows={})


def _f(canonical: str, col: str, row: int, *,
        confidence: Confidence = Confidence.HIGH) -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col, 2),
        value_coord=(col, row), value="v",
        confidence=confidence, evidence=[],
    )


def _stage(canonical: str | None = None) -> FinalStage:
    return FinalStage(
        name="Sample Inspection", canonical=canonical,
        plan_date=dt.date(2026, 5, 1), plan_date_col=4,
        column_range=(4, 6), stage_metadata={},
    )


def _entry(canonical: str | None = None) -> MetadataEntry:
    return MetadataEntry(key="Treatment", value="Garment Dye",
                          source="K4", canonical=canonical)


def _run_quiet(pipeline: Pipeline, *,
                findings=None, stages=None, metadata=None,
                warnings=None) -> dict:
    """Drive the pipeline with quiet inputs (no warnings, no triggers)."""
    bundle = _bundle()
    findings = findings if findings is not None else []
    stages = stages if stages is not None else {}
    metadata = metadata if metadata is not None else []
    warnings = warnings if warnings is not None else []
    return pipeline.run({
        "identifier_finding": {"findings": findings, "warnings": warnings, "bundle": bundle},
        "identifier_phase":   {"raw_findings": findings, "warnings": warnings, "bundle": bundle},
        "stage_finding":      {"stages_per_row": stages, "bundle": bundle},
        "stage_phase":        {"raw_stages_per_row": stages, "warnings": warnings, "bundle": bundle},
        "metadata":           {"metadata_entries": metadata, "bundle": bundle},
    })


# ─── Factory shape ───────────────────────────────────────────────────────


def test_factory_returns_pipeline_with_five_gates() -> None:
    pipeline = make_canvas_judges_pipeline(llm=FakeLLM(canned={}))
    assert isinstance(pipeline, Pipeline)
    expected = {
        "identifier_finding", "stage_finding", "metadata",
        "identifier_phase",   "stage_phase",
    }
    assert set(pipeline.graph.nodes) == expected


def test_factory_wires_audits_to_phase_gates() -> None:
    pipeline = make_canvas_judges_pipeline(llm=FakeLLM(canned={}))
    edge_pairs = {(u, v) for (u, v, _key) in pipeline.graph.edges}
    assert ("identifier_finding", "identifier_phase") in edge_pairs
    assert ("stage_finding",      "stage_phase") in edge_pairs


def test_factory_returns_fresh_pipelines_each_call() -> None:
    p1 = make_canvas_judges_pipeline(llm=FakeLLM(canned={}))
    p2 = make_canvas_judges_pipeline(llm=FakeLLM(canned={}))
    assert p1 is not p2
    assert set(p1.graph.nodes) == set(p2.graph.nodes)


# ─── End-to-end (quiet path — no LLM calls) ──────────────────────────────


def test_quiet_run_returns_clean_outputs() -> None:
    """No warnings, no novel canonicals, all-high-confidence findings.

    The per-finding gates don't route anything; the phase gates short-circuit
    via the pass-through path. Zero LLM calls — using FakeLLM with no canned
    responses confirms this: any call would raise.
    """
    pipeline = make_canvas_judges_pipeline(llm=FakeLLM(canned={}))
    findings = [_f("io_number", "A", 3)]
    stages = {3: [_stage(canonical="fabric")]}
    metadata = [_entry(canonical="buyer")]

    result = _run_quiet(pipeline, findings=findings, stages=stages, metadata=metadata)

    assert result["identifier_phase"]["findings"] == findings
    assert result["stage_phase"]["stages_per_row"] == stages
    assert result["metadata"]["metadata_entries"] == metadata


def test_quiet_run_empty_inputs_yields_empty_outputs() -> None:
    pipeline = make_canvas_judges_pipeline(llm=FakeLLM(canned={}))
    result = _run_quiet(pipeline)
    assert result["identifier_phase"]["findings"] == []
    assert result["stage_phase"]["stages_per_row"] == {}
    assert result["metadata"]["metadata_entries"] == []


# ─── End-to-end with a routed finding ────────────────────────────────────


def test_low_confidence_finding_routes_through_identifier_chain() -> None:
    """LOW confidence triggers per-finding judge; no warnings → phase is pass-through."""
    canned = {
        "IdentifierVerdict": {
            "decision": "keep", "alternative_coord": None,
            "reason": "value matches spec", "confidence": "high",
        },
    }
    pipeline = make_canvas_judges_pipeline(llm=FakeLLM(canned=canned))
    findings = [_f("io_number", "A", 3, confidence=Confidence.LOW)]
    result = _run_quiet(pipeline, findings=findings)
    # The judge said keep → finding survives
    assert len(result["identifier_phase"]["findings"]) == 1


def test_warning_triggers_phase_gate_with_no_decisions() -> None:
    """Warning fires phase judge; verdict is empty → post-per-finding bag returns."""
    canned = {
        "IdentifierPhaseVerdict": {
            "decisions": [], "summary": "no overrides needed", "confidence": "high",
        },
    }
    pipeline = make_canvas_judges_pipeline(llm=FakeLLM(canned=canned))
    findings = [_f("io_number", "A", 3)]
    warning = ValidationWarning(name="x", severity="warning", message="y")
    result = _run_quiet(pipeline, findings=findings, warnings=[warning])
    assert len(result["identifier_phase"]["findings"]) == 1


# ─── Stage chain ─────────────────────────────────────────────────────────


def test_novel_stage_routes_through_stage_chain() -> None:
    canned = {
        "StageVerdict": {
            "decision": "rewrite", "alternative_canonical": "fabric",
            "reason": "matches alias", "confidence": "high",
        },
    }
    pipeline = make_canvas_judges_pipeline(llm=FakeLLM(canned=canned))
    stages = {3: [_stage(canonical=None)]}
    result = _run_quiet(pipeline, stages=stages)
    adjudicated = result["stage_phase"]["stages_per_row"][3][0]
    assert adjudicated.canonical == "fabric"


# ─── Metadata branch ─────────────────────────────────────────────────────


def test_novel_metadata_routes_through_metadata_gate() -> None:
    canned = {
        "MetadataVerdict": {
            "decision": "keep", "alternative_canonical": None,
            "reason": "novel label", "confidence": "medium",
        },
    }
    pipeline = make_canvas_judges_pipeline(llm=FakeLLM(canned=canned))
    metadata = [_entry(canonical=None)]
    result = _run_quiet(pipeline, metadata=metadata)
    assert len(result["metadata"]["metadata_entries"]) == 1
    assert result["metadata"]["metadata_entries"][0].canonical is None
