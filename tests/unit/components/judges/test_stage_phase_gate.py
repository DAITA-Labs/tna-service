"""StagePhaseGate — bag-level arbitration on top of per-stage judging."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.agents.judges.stage_finding.schema import StageFindingAudit, StageVerdict
from app.agents.judges.stage_phase.schema import StageDecision
from app.artifacts.finding import ValidationWarning
from app.components.judges.stage_phase_gate import (
    StagePhaseGate,
    _apply_audits,
    _apply_phase_decisions,
    _should_invoke,
)
from app.specs.schemas import FinalStage
from tests.fixtures.fake_llm import FakeLLM
from tests.unit.components.field._bundles import make_bundle


def _bundle():
    return make_bundle([[None] * 5 for _ in range(8)], "io_number", columns={}, rows={})


def _stage(**overrides) -> FinalStage:
    base = dict(
        name="Sample Inspection",
        canonical=None,
        plan_date=dt.date(2026, 5, 1),
        plan_date_col=4,
        column_range=(4, 6),
        stage_metadata={},
    )
    base.update(overrides)
    return FinalStage(**base)


def _ok_phase_verdict(decisions=None) -> dict:
    return {
        "decisions": decisions or [],
        "summary": "phase ok",
        "confidence": "high",
    }


# ─── Pass-through path (no LLM) ──────────────────────────────────────────


def test_no_warnings_and_no_failures_skips_llm() -> None:
    stages = {3: [_stage(canonical="fabric")]}
    gate = StagePhaseGate(llm=FakeLLM(canned={}))    # no canned — would crash if invoked
    out = gate.run(raw_stages_per_row=stages, audits=[], warnings=[], bundle=_bundle())
    assert out["stages_per_row"] == stages


def test_audit_rewrite_applied_to_pass_through() -> None:
    """Per-stage audit's verdict rewrites canonical when no LLM fires."""
    audit = StageFindingAudit(
        row=3, stage_index=0,
        verdict=StageVerdict(decision="rewrite", alternative_canonical="fabric",
                              reason="x", confidence="high"),
    )
    gate = StagePhaseGate(llm=FakeLLM(canned={}))
    out = gate.run(raw_stages_per_row={3: [_stage()]}, audits=[audit],
                    warnings=[], bundle=_bundle())
    assert out["stages_per_row"][3][0].canonical == "fabric"


# ─── Phase judge invocation ──────────────────────────────────────────────


def test_warnings_present_invokes_phase_judge() -> None:
    stages = {3: [_stage()]}
    warning = ValidationWarning(name="stage_sequence_inversion",
                                 severity="warning", message="z")
    llm = FakeLLM(canned={"StagePhaseVerdict": _ok_phase_verdict()})
    gate = StagePhaseGate(llm=llm)
    out = gate.run(raw_stages_per_row=stages, audits=[], warnings=[warning], bundle=_bundle())
    assert len(out["stages_per_row"][3]) == 1


def test_phase_drop_decision_removes_stage() -> None:
    audit = StageFindingAudit(
        row=3, stage_index=0,
        verdict=StageVerdict(decision="keep", reason="x", confidence="high"),
    )
    warning = ValidationWarning(name="x", severity="warning", message="y")
    llm = FakeLLM(canned={"StagePhaseVerdict": _ok_phase_verdict(decisions=[
        {"row": 3, "stage_index": 0, "decision": "drop", "reason": "z"},
    ])})
    gate = StagePhaseGate(llm=llm)
    out = gate.run(raw_stages_per_row={3: [_stage()]}, audits=[audit],
                    warnings=[warning], bundle=_bundle())
    assert out["stages_per_row"][3] == []


def test_phase_rewrite_sets_canonical_and_judge_action() -> None:
    audit = StageFindingAudit(row=3, stage_index=0, judge_failed=True)
    llm = FakeLLM(canned={"StagePhaseVerdict": _ok_phase_verdict(decisions=[
        {"row": 3, "stage_index": 0, "decision": "rewrite",
         "alternative_canonical": "fabric", "reason": "matches"},
    ])})
    gate = StagePhaseGate(llm=llm)
    out = gate.run(raw_stages_per_row={3: [_stage()]}, audits=[audit],
                    warnings=[], bundle=_bundle())
    rewritten = out["stages_per_row"][3][0]
    assert rewritten.canonical == "fabric"
    assert rewritten.judge_action == "phase_canonical_set_to_fabric"


# ─── Fail-safe ───────────────────────────────────────────────────────────


def test_phase_judge_agent_run_failure_keeps_post_per_stage_map() -> None:
    audit = StageFindingAudit(
        row=3, stage_index=0,
        verdict=StageVerdict(decision="keep", reason="x", confidence="high"),
    )
    warning = ValidationWarning(name="x", severity="warning", message="y")
    bad = {"decisions": [
        {"row": 3, "stage_index": 0, "decision": "rewrite",
         "alternative_canonical": "made_up", "reason": "x"},
    ], "summary": "...", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad, bad)
    gate = StagePhaseGate(llm=llm)
    out = gate.run(raw_stages_per_row={3: [_stage()]}, audits=[audit],
                    warnings=[warning], bundle=_bundle())
    assert len(out["stages_per_row"][3]) == 1
    assert out["stages_per_row"][3][0].canonical is None    # per-stage said keep


# ─── Helpers ─────────────────────────────────────────────────────────────


def test_should_invoke_returns_false_when_quiet() -> None:
    assert not _should_invoke([], [])


def test_should_invoke_returns_true_for_warnings() -> None:
    assert _should_invoke([ValidationWarning(name="x", severity="warning", message="y")], [])


def test_should_invoke_returns_true_for_failed_audit() -> None:
    assert _should_invoke([], [StageFindingAudit(row=3, stage_index=0, judge_failed=True)])


def test_apply_audits_drops_via_verdict() -> None:
    raw = {3: [_stage()]}
    audit = StageFindingAudit(
        row=3, stage_index=0,
        verdict=StageVerdict(decision="drop", reason="x", confidence="high"),
    )
    out = _apply_audits(raw, [audit])
    assert out[3] == []


def test_apply_audits_keeps_unjudged_stages() -> None:
    raw = {3: [_stage(canonical="fabric")]}
    out = _apply_audits(raw, [])
    assert out == raw


def test_apply_phase_decisions_overrides_post_state() -> None:
    raw = {3: [_stage()]}
    decision = StageDecision(row=3, stage_index=0, decision="drop", reason="x")
    out = _apply_phase_decisions(raw, [decision], post_stage=raw)
    assert out[3] == []


# ─── Component plumbing ──────────────────────────────────────────────────


def test_gate_sockets_registered() -> None:
    gate = StagePhaseGate(llm=FakeLLM(canned={}))
    inputs = gate.__haystack_input__._sockets_dict
    for socket in ("raw_stages_per_row", "audits", "warnings", "bundle"):
        assert socket in inputs, f"missing input socket {socket}"
    assert "stages_per_row" in gate.__haystack_output__._sockets_dict


def test_gate_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("phase", StagePhaseGate(llm=FakeLLM(canned={})))
    assert "phase" in pipeline.graph.nodes
