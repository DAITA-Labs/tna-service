"""StageFindingJudge build_input + retry behaviour with FakeLLM."""
from __future__ import annotations

import datetime as dt

from app.agents._base import AgentRunFailure
from app.agents.judges.stage_finding import StageFindingJudge
from app.agents.judges.stage_finding.schema import (
    StageFindingForJudge,
    StageVerdict,
)
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


def _inputs(**overrides) -> StageFindingForJudge:
    base = dict(
        stage=_stage(),
        row=3,
        stage_catalog="- fabric — aliases: fab, fabric",
        sheet_excerpt="...",
    )
    base.update(overrides)
    return StageFindingForJudge(**base)


# ─── build_input ─────────────────────────────────────────────────────────


def test_build_input_includes_stage_block_and_catalog() -> None:
    text = StageFindingJudge().build_input(ctx=None, inputs=_inputs())
    assert "## Stage under review" in text
    assert "Sample Inspection" in text
    assert "pli_row:        3" in text
    assert "## Stage catalog" in text


def test_build_input_renders_stage_metadata_only_when_present() -> None:
    no_meta = StageFindingJudge().build_input(ctx=None, inputs=_inputs())
    assert "stage_metadata:" not in no_meta

    with_meta = StageFindingJudge().build_input(
        ctx=None,
        inputs=_inputs(stage=_stage(stage_metadata={"actual_date": "2026-05-02"})),
    )
    assert "stage_metadata:" in with_meta
    assert "actual_date" in with_meta


def test_build_input_includes_cluster_context_when_set() -> None:
    text = StageFindingJudge().build_input(
        ctx=None, inputs=_inputs(cluster_context="cluster_id=c0 sheet=Plan"),
    )
    assert "## Cluster context" in text


# ─── End-to-end with FakeLLM ─────────────────────────────────────────────


def test_keep_verdict_returns_validated_output() -> None:
    canned = {"StageVerdict": {
        "decision": "keep", "alternative_canonical": None,
        "reason": "genuinely novel label", "confidence": "high",
    }}
    result = StageFindingJudge().run(ctx=None, inputs=_inputs(), provider=FakeLLM(canned=canned))
    assert isinstance(result, StageVerdict)
    assert result.decision == "keep"


def test_rewrite_verdict_with_valid_canonical_returns_output() -> None:
    canned = {"StageVerdict": {
        "decision": "rewrite", "alternative_canonical": "fabric",
        "reason": "matches fabric alias", "confidence": "high",
    }}
    result = StageFindingJudge().run(ctx=None, inputs=_inputs(), provider=FakeLLM(canned=canned))
    assert isinstance(result, StageVerdict)
    assert result.alternative_canonical == "fabric"


def test_hallucinated_canonical_triggers_retry_then_succeeds() -> None:
    bad  = {"decision": "rewrite", "alternative_canonical": "made_up_stage",
            "reason": "x", "confidence": "high"}
    good = {"decision": "rewrite", "alternative_canonical": "fabric",
            "reason": "x", "confidence": "high"}
    llm = FakeLLM(canned={}).script_responses(bad, good)
    result = StageFindingJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, StageVerdict)
    assert result.alternative_canonical == "fabric"


def test_two_invalid_canonicals_yield_agent_run_failure() -> None:
    bad1 = {"decision": "rewrite", "alternative_canonical": "fake1",
            "reason": "x", "confidence": "low"}
    bad2 = {"decision": "rewrite", "alternative_canonical": "fake2",
            "reason": "x", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad1, bad2)
    result = StageFindingJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, AgentRunFailure)


# ─── Class attributes ────────────────────────────────────────────────────


def test_agent_uses_stage_finding_judge_prompt() -> None:
    from app.prompts import STAGE_FINDING_JUDGE
    assert StageFindingJudge.prompt is STAGE_FINDING_JUDGE


def test_agent_name_used_for_telemetry_keys() -> None:
    assert StageFindingJudge.name == "stage_finding_judge"
