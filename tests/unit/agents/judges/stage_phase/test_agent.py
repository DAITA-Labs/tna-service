"""StagePhaseJudge build_input + retry behaviour with FakeLLM."""
from __future__ import annotations

import datetime as dt

from app.agents._base import AgentRunFailure
from app.agents.judges.stage_finding.schema import StageFindingAudit, StageVerdict
from app.agents.judges.stage_phase import StagePhaseJudge
from app.agents.judges.stage_phase.schema import (
    StagePhaseForJudge,
    StagePhaseVerdict,
)
from app.artifacts.finding import ValidationWarning
from app.specs.schemas import FinalStage
from tests.fixtures.fake_llm import FakeLLM


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


def _inputs(**overrides) -> StagePhaseForJudge:
    base = dict(
        raw_stages_per_row={3: [_stage()]},
        audits=[],
        warnings=[],
        sheet_summary="cluster_id=c0 sheet=Plan",
    )
    base.update(overrides)
    return StagePhaseForJudge(**base)


def _ok_verdict() -> dict:
    return {"decisions": [], "summary": "no overrides needed", "confidence": "high"}


# ─── build_input ─────────────────────────────────────────────────────────


def test_build_input_lists_stages_with_indices() -> None:
    text = StagePhaseJudge().build_input(ctx=None, inputs=_inputs())
    assert "### Row 3" in text
    assert "[0] name='Sample Inspection'" in text


def test_build_input_marks_stages_not_routed() -> None:
    text = StagePhaseJudge().build_input(ctx=None, inputs=_inputs())
    assert "not routed to per-stage judge" in text


def test_build_input_renders_audit_when_present() -> None:
    audit = StageFindingAudit(
        row=3, stage_index=0,
        verdict=StageVerdict(decision="rewrite", alternative_canonical="fabric",
                              reason="alias matches", confidence="high"),
    )
    text = StagePhaseJudge().build_input(ctx=None, inputs=_inputs(audits=[audit]))
    assert "per-stage said REWRITE→canonical=fabric" in text


def test_build_input_marks_judge_failure() -> None:
    audit = StageFindingAudit(row=3, stage_index=0, verdict=None, judge_failed=True)
    text = StagePhaseJudge().build_input(ctx=None, inputs=_inputs(audits=[audit]))
    assert "per-stage judge failed" in text


def test_build_input_includes_warnings_and_catalog() -> None:
    warning = ValidationWarning(name="unrecognised_stage", severity="info",
                                  message="novel label")
    text = StagePhaseJudge().build_input(
        ctx=None, inputs=_inputs(warnings=[warning], stage_catalog="- fabric — aliases: fab"),
    )
    assert "## Residual validator warnings" in text
    assert "unrecognised_stage" in text
    assert "## Stage catalog" in text


# ─── End-to-end with FakeLLM ─────────────────────────────────────────────


def test_empty_verdict_returns_validated_output() -> None:
    llm = FakeLLM(canned={"StagePhaseVerdict": _ok_verdict()})
    result = StagePhaseJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, StagePhaseVerdict)
    assert result.decisions == []


def test_duplicate_pair_triggers_retry_then_succeeds() -> None:
    bad = {"decisions": [
        {"row": 3, "stage_index": 0, "decision": "keep", "reason": "x"},
        {"row": 3, "stage_index": 0, "decision": "drop", "reason": "y"},
    ], "summary": "...", "confidence": "high"}
    good = _ok_verdict()
    llm = FakeLLM(canned={}).script_responses(bad, good)
    result = StagePhaseJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, StagePhaseVerdict)


def test_two_invalid_responses_yield_agent_run_failure() -> None:
    bad = {"decisions": [
        {"row": 3, "stage_index": 0, "decision": "rewrite",
         "alternative_canonical": "made_up", "reason": "x"},
    ], "summary": "...", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad, bad)
    result = StagePhaseJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, AgentRunFailure)


# ─── Class attributes ────────────────────────────────────────────────────


def test_agent_uses_stage_phase_prompt() -> None:
    from app.prompts import STAGE_PHASE_JUDGE
    assert StagePhaseJudge.prompt is STAGE_PHASE_JUDGE


def test_agent_name_used_for_telemetry_keys() -> None:
    assert StagePhaseJudge.name == "stage_phase_judge"
