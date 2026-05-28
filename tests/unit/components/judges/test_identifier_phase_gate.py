"""IdentifierPhaseGate — bag-level arbitration on top of per-finding judging."""
from __future__ import annotations

from haystack import Pipeline

from app.agents.judges.identifier_finding.schema import (
    IdentifierFindingAudit,
    IdentifierVerdict,
)
from app.artifacts.finding import Confidence, Finding, ValidationWarning
from app.components.judges.identifier_phase_gate import (
    IdentifierPhaseGate,
    _apply_audits,
    _apply_phase_decisions,
    _should_invoke,
)
from app.agents.judges.identifier_phase.schema import FindingDecision
from tests.fixtures.fake_llm import FakeLLM
from tests.unit.components.field._bundles import make_bundle


def _bundle(overlay: dict[tuple[int, int], object] | None = None):
    values = [[None] * 5 for _ in range(8)]
    for (r, c), v in (overlay or {}).items():
        values[r - 1][c - 1] = v
    return make_bundle(values, "io_number", columns={}, rows={})


def _f(canonical: str, col: str, row: int, *,
        value: object = "v",
        confidence: Confidence = Confidence.HIGH) -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col, 2),
        value_coord=(col, row), value=value,
        confidence=confidence, evidence=[],
    )


def _ok_phase_verdict(decisions=None) -> dict:
    return {
        "decisions": decisions or [],
        "summary": "phase ok",
        "confidence": "high",
    }


# ─── Pass-through path (no LLM) ──────────────────────────────────────────


def test_no_warnings_and_no_failures_skips_llm() -> None:
    """Empty warnings + no judge failures → return post-per-finding bag without invoking."""
    findings = [_f("io_number", "A", 3)]
    gate = IdentifierPhaseGate(llm=FakeLLM(canned={}))    # no canned response — would crash if called
    out = gate.run(raw_findings=findings, audits=[], warnings=[], bundle=_bundle())
    assert out["findings"] == findings


def test_audit_drop_applied_to_pass_through() -> None:
    """When the per-finding audit says drop, the pass-through bag drops the finding."""
    finding = _f("io_number", "A", 3, confidence=Confidence.LOW)
    audit = IdentifierFindingAudit(
        finding_index=0,
        verdict=IdentifierVerdict(decision="drop", reason="x", confidence="high"),
    )
    gate = IdentifierPhaseGate(llm=FakeLLM(canned={}))
    out = gate.run(raw_findings=[finding], audits=[audit], warnings=[], bundle=_bundle())
    assert out["findings"] == []


# ─── Phase judge invocation ──────────────────────────────────────────────


def test_warnings_present_invokes_phase_judge() -> None:
    """Any warning → phase judge runs even when audits are empty."""
    finding = _f("io_number", "A", 3)
    warning = ValidationWarning(
        name="missing_mandatory_io_number", severity="error", message="row 4 missing",
    )
    llm = FakeLLM(canned={"IdentifierPhaseVerdict": _ok_phase_verdict()})
    gate = IdentifierPhaseGate(llm=llm)
    out = gate.run(raw_findings=[finding], audits=[], warnings=[warning], bundle=_bundle())
    # No decisions → finding survives.
    assert len(out["findings"]) == 1


def test_judge_failure_in_audit_invokes_phase_judge() -> None:
    """Any `judge_failed=True` audit triggers phase judging even with no warnings."""
    finding = _f("io_number", "A", 3, confidence=Confidence.LOW)
    audit = IdentifierFindingAudit(finding_index=0, judge_failed=True)
    llm = FakeLLM(canned={"IdentifierPhaseVerdict": _ok_phase_verdict()})
    gate = IdentifierPhaseGate(llm=llm)
    out = gate.run(raw_findings=[finding], audits=[audit], warnings=[], bundle=_bundle())
    assert len(out["findings"]) == 1


# ─── Phase decisions apply ───────────────────────────────────────────────


def test_phase_drop_decision_overrides_keep() -> None:
    """Per-finding said keep; phase says drop — drop wins."""
    finding = _f("io_number", "A", 3, confidence=Confidence.LOW)
    audit = IdentifierFindingAudit(
        finding_index=0,
        verdict=IdentifierVerdict(decision="keep", reason="x", confidence="high"),
    )
    warning = ValidationWarning(name="x", severity="warning", message="y")
    llm = FakeLLM(canned={"IdentifierPhaseVerdict": _ok_phase_verdict(decisions=[
        {"finding_index": 0, "decision": "drop", "reason": "phase override"},
    ])})
    gate = IdentifierPhaseGate(llm=llm)
    out = gate.run(raw_findings=[finding], audits=[audit], warnings=[warning], bundle=_bundle())
    assert out["findings"] == []


def test_phase_keep_overrides_per_finding_drop() -> None:
    """Per-finding said drop; phase says keep — finding survives."""
    finding = _f("io_number", "A", 3, confidence=Confidence.LOW)
    audit = IdentifierFindingAudit(
        finding_index=0,
        verdict=IdentifierVerdict(decision="drop", reason="x", confidence="medium"),
    )
    warning = ValidationWarning(name="missing_mandatory_io_number",
                                  severity="error", message="y")
    llm = FakeLLM(canned={"IdentifierPhaseVerdict": _ok_phase_verdict(decisions=[
        {"finding_index": 0, "decision": "keep", "reason": "cardinality requires it"},
    ])})
    gate = IdentifierPhaseGate(llm=llm)
    out = gate.run(raw_findings=[finding], audits=[audit], warnings=[warning], bundle=_bundle())
    assert len(out["findings"]) == 1
    assert out["findings"][0].value_coord == ("A", 3)


def test_phase_rewrite_reads_canvas_and_tags_evidence() -> None:
    finding = _f("io_number", "A", 3, confidence=Confidence.LOW)
    audit = IdentifierFindingAudit(
        finding_index=0,
        verdict=IdentifierVerdict(decision="keep", reason="x", confidence="medium"),
    )
    warning = ValidationWarning(name="x", severity="warning", message="y")
    llm = FakeLLM(canned={"IdentifierPhaseVerdict": _ok_phase_verdict(decisions=[
        {"finding_index": 0, "decision": "rewrite",
         "alternative_coord": ("B", 3), "reason": "real io is at B3"},
    ])})
    bundle = _bundle(overlay={(3, 2): "IO-9012"})
    gate = IdentifierPhaseGate(llm=llm)
    out = gate.run(raw_findings=[finding], audits=[audit], warnings=[warning], bundle=bundle)
    assert len(out["findings"]) == 1
    rewritten = out["findings"][0]
    assert rewritten.value_coord == ("B", 3)
    assert rewritten.value == "IO-9012"
    assert "phase_judge_rewrite" in rewritten.evidence


def test_phase_no_decision_for_finding_falls_back_to_per_finding_state() -> None:
    """Findings the phase judge doesn't speak about retain their per-finding outcome."""
    finding_a = _f("io_number",  "A", 3, confidence=Confidence.HIGH)    # clean
    finding_b = _f("style_code", "B", 3, confidence=Confidence.LOW)     # judged
    audit = IdentifierFindingAudit(
        finding_index=1,
        verdict=IdentifierVerdict(decision="drop", reason="x", confidence="high"),
    )
    warning = ValidationWarning(name="x", severity="warning", message="y")
    llm = FakeLLM(canned={"IdentifierPhaseVerdict": _ok_phase_verdict()})  # no overrides
    gate = IdentifierPhaseGate(llm=llm)
    out = gate.run(raw_findings=[finding_a, finding_b], audits=[audit],
                    warnings=[warning], bundle=_bundle())
    canonicals = [f.canonical for f in out["findings"]]
    assert canonicals == ["io_number"]    # style dropped by per-finding, phase didn't override


# ─── Fail-safe ───────────────────────────────────────────────────────────


def test_phase_judge_agent_run_failure_keeps_post_per_finding_bag() -> None:
    """Two invalid phase responses → AgentRunFailure → post-per-finding bag is returned."""
    finding = _f("io_number", "A", 3)
    audit = IdentifierFindingAudit(
        finding_index=0,
        verdict=IdentifierVerdict(decision="keep", reason="x", confidence="high"),
    )
    warning = ValidationWarning(name="x", severity="warning", message="y")
    bad = {"decisions": [
        {"finding_index": 0, "decision": "rewrite", "alternative_coord": None,
         "reason": "x"},
    ], "summary": "...", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad, bad)
    gate = IdentifierPhaseGate(llm=llm)
    out = gate.run(raw_findings=[finding], audits=[audit], warnings=[warning], bundle=_bundle())
    assert len(out["findings"]) == 1


# ─── Helpers ─────────────────────────────────────────────────────────────


def test_should_invoke_returns_false_when_quiet() -> None:
    assert not _should_invoke([], [])


def test_should_invoke_returns_true_for_warnings() -> None:
    assert _should_invoke([ValidationWarning(name="x", severity="warning", message="y")], [])


def test_should_invoke_returns_true_for_failed_audit() -> None:
    assert _should_invoke([], [IdentifierFindingAudit(finding_index=0, judge_failed=True)])


def test_apply_audits_keeps_unjudged_findings() -> None:
    findings = [_f("io_number", "A", 3), _f("style_code", "B", 3)]
    out = _apply_audits(findings, audits=[], canvas=_bundle().canvas)
    assert out == findings


def test_apply_audits_drops_via_verdict() -> None:
    findings = [_f("io_number", "A", 3)]
    audit = IdentifierFindingAudit(
        finding_index=0,
        verdict=IdentifierVerdict(decision="drop", reason="x", confidence="high"),
    )
    out = _apply_audits(findings, [audit], canvas=_bundle().canvas)
    assert out == []


def test_apply_audits_keeps_finding_on_judge_failed_audit() -> None:
    findings = [_f("io_number", "A", 3)]
    audit = IdentifierFindingAudit(finding_index=0, verdict=None, judge_failed=True)
    out = _apply_audits(findings, [audit], canvas=_bundle().canvas)
    assert out == findings


def test_apply_phase_decisions_overrides_post_state() -> None:
    findings = [_f("io_number", "A", 3)]
    decisions = [FindingDecision(finding_index=0, decision="drop", reason="x")]
    out = _apply_phase_decisions(findings, decisions, post_finding=findings,
                                    canvas=_bundle().canvas)
    assert out == []


# ─── Component plumbing ──────────────────────────────────────────────────


def test_gate_sockets_registered() -> None:
    gate = IdentifierPhaseGate(llm=FakeLLM(canned={}))
    inputs = gate.__haystack_input__._sockets_dict
    for socket in ("raw_findings", "audits", "warnings", "bundle"):
        assert socket in inputs, f"missing input socket {socket}"
    assert "findings" in gate.__haystack_output__._sockets_dict


def test_gate_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("phase", IdentifierPhaseGate(llm=FakeLLM(canned={})))
    assert "phase" in pipeline.graph.nodes
