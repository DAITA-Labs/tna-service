"""PlanReviewerInputs and PlanVerdict schema tests."""
from __future__ import annotations

from app.agents.plan_reviewer.schema import PlanReviewerInputs, PlanVerdict
from app.artifacts.agent_io import AgentOutput
from app.enums.pli_mode import PliMode
from app.models.artifacts import SheetPlan


def _minimal_plan() -> SheetPlan:
    return SheetPlan(sheet="Sheet1", pli_mode=PliMode.ROW_PER_PLI)


def test_verdict_inherits_agent_output() -> None:
    assert issubclass(PlanVerdict, AgentOutput)


def test_verdict_defaults() -> None:
    out = PlanVerdict()
    assert out.verdict == "looks_correct"
    assert out.row_corrections == []
    assert out.identity_column_suggestion is None
    assert out.warnings == []
    assert out.confidence == 1.0
    assert out.decision_notes is None


def test_verdict_round_trip() -> None:
    out = PlanVerdict(
        verdict="needs_fix",
        row_corrections=[{"row": 5, "suggested_role": "anchor", "reason": "merged cell"}],
        identity_column_suggestion="B",
        warnings=["stage band overlaps"],
        confidence=0.75,
    )
    dumped = out.model_dump()
    restored = PlanVerdict(**dumped)
    assert restored.verdict == "needs_fix"
    assert restored.row_corrections[0]["row"] == 5
    assert restored.identity_column_suggestion == "B"
    assert restored.warnings == ["stage band overlaps"]
    assert restored.confidence == 0.75


def test_inputs_wraps_plan() -> None:
    plan = _minimal_plan()
    inputs = PlanReviewerInputs(plan=plan)
    assert inputs.plan is plan
    assert inputs.findings == []
