"""IdentifierPhaseJudge build_input + retry behaviour with FakeLLM."""
from __future__ import annotations

from app.agents._base import AgentRunFailure
from app.agents.judges.identifier_finding.schema import (
    IdentifierFindingAudit,
    IdentifierVerdict,
)
from app.agents.judges.identifier_phase import IdentifierPhaseJudge
from app.agents.judges.identifier_phase.schema import (
    IdentifierPhaseForJudge,
    IdentifierPhaseVerdict,
)
from app.artifacts.finding import Confidence, Finding, ValidationWarning
from tests.fixtures.fake_llm import FakeLLM


def _f(canonical: str, col: str, row: int) -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col, 2),
        value_coord=(col, row), value="v",
        confidence=Confidence.MEDIUM, evidence=[],
    )


def _inputs(**overrides) -> IdentifierPhaseForJudge:
    base = dict(
        raw_findings=[_f("io_number", "A", 3), _f("style_code", "B", 3)],
        audits=[],
        warnings=[],
        pli_rows=[3],
        sheet_summary="cluster_id=c0 sheet=Plan",
    )
    base.update(overrides)
    return IdentifierPhaseForJudge(**base)


def _ok_verdict() -> dict:
    return {"decisions": [], "summary": "no overrides needed", "confidence": "high"}


# ─── build_input ─────────────────────────────────────────────────────────


def test_build_input_lists_raw_findings_with_index() -> None:
    text = IdentifierPhaseJudge().build_input(ctx=None, inputs=_inputs())
    assert "[0] io_number" in text
    assert "[1] style_code" in text


def test_build_input_marks_findings_not_routed() -> None:
    text = IdentifierPhaseJudge().build_input(ctx=None, inputs=_inputs())
    assert "not routed to per-finding judge" in text


def test_build_input_renders_audit_when_present() -> None:
    audit = IdentifierFindingAudit(
        finding_index=1,
        verdict=IdentifierVerdict(decision="drop", reason="header is STYLE NO",
                                    confidence="high"),
    )
    text = IdentifierPhaseJudge().build_input(ctx=None, inputs=_inputs(audits=[audit]))
    assert "per-finding said DROP" in text
    assert "header is STYLE NO" in text


def test_build_input_marks_judge_failure() -> None:
    audit = IdentifierFindingAudit(finding_index=0, verdict=None, judge_failed=True)
    text = IdentifierPhaseJudge().build_input(ctx=None, inputs=_inputs(audits=[audit]))
    assert "per-finding judge failed" in text


def test_build_input_includes_warnings_with_affects_indices() -> None:
    findings = [_f("io_number", "A", 3), _f("style_code", "B", 3)]
    warning = ValidationWarning(
        name="anti_pattern_match", severity="warning",
        message="suspicious header", affects_findings=[findings[1]],
    )
    text = IdentifierPhaseJudge().build_input(
        ctx=None, inputs=_inputs(raw_findings=findings, warnings=[warning]),
    )
    assert "Residual validator warnings" in text
    assert "affects: [1]" in text


def test_build_input_includes_spec_snippets() -> None:
    text = IdentifierPhaseJudge().build_input(
        ctx=None, inputs=_inputs(spec_snippets={"io_number": "primary order id"}),
    )
    assert "## Spec snippets" in text
    assert "io_number" in text
    assert "primary order id" in text


# ─── End-to-end with FakeLLM ─────────────────────────────────────────────


def test_empty_verdict_returns_validated_output() -> None:
    llm = FakeLLM(canned={"IdentifierPhaseVerdict": _ok_verdict()})
    result = IdentifierPhaseJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, IdentifierPhaseVerdict)
    assert result.decisions == []


def test_duplicate_indices_trigger_retry_then_succeed() -> None:
    bad = {"decisions": [
        {"finding_index": 0, "decision": "keep", "reason": "x"},
        {"finding_index": 0, "decision": "drop", "reason": "y"},
    ], "summary": "...", "confidence": "high"}
    good = _ok_verdict()
    llm = FakeLLM(canned={}).script_responses(bad, good)
    result = IdentifierPhaseJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, IdentifierPhaseVerdict)


def test_two_invalid_responses_yield_agent_run_failure() -> None:
    bad = {"decisions": [
        {"finding_index": 0, "decision": "rewrite", "alternative_coord": None,
         "reason": "x"},
    ], "summary": "...", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad, bad)
    result = IdentifierPhaseJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, AgentRunFailure)


# ─── Class attributes ────────────────────────────────────────────────────


def test_agent_uses_identifier_phase_prompt() -> None:
    from app.prompts import IDENTIFIER_PHASE_JUDGE
    assert IdentifierPhaseJudge.prompt is IDENTIFIER_PHASE_JUDGE


def test_agent_name_used_for_telemetry_keys() -> None:
    assert IdentifierPhaseJudge.name == "identifier_phase_judge"
