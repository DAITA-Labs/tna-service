"""IdentifierFindingJudge build_input + retry behaviour with FakeLLM."""
from __future__ import annotations

from app.agents._base import AgentRunFailure
from app.agents.judges.identifier_finding import IdentifierFindingJudge
from app.agents.judges.identifier_finding.schema import (
    FindingForJudge,
    IdentifierVerdict,
)
from app.artifacts.finding import Confidence, Finding, ValidationWarning
from tests.fixtures.fake_llm import FakeLLM


def _finding(canonical: str = "io_number",
              col: str = "A", row: int = 3,
              confidence: Confidence = Confidence.LOW) -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col, 2),
        value_coord=(col, row), value="IO-1",
        confidence=confidence, evidence=["TABULAR_HEADER_MATCH"],
    )


def _inputs(**overrides) -> FindingForJudge:
    base = dict(
        finding=_finding(),
        sheet_excerpt="A3: IO-1\nB3: Navy",
        spec_snippet="io_number — primary order identifier",
    )
    base.update(overrides)
    return FindingForJudge(**base)


# ─── build_input ─────────────────────────────────────────────────────────


def test_build_input_includes_finding_block() -> None:
    text = IdentifierFindingJudge().build_input(ctx=None, inputs=_inputs())
    assert "## Finding under review" in text
    assert "canonical:  io_number" in text
    assert "value_coord: A3" in text
    assert "confidence: low" in text


def test_build_input_renders_spec_snippet_and_excerpt() -> None:
    text = IdentifierFindingJudge().build_input(ctx=None, inputs=_inputs())
    assert "## Spec snippet" in text
    assert "primary order identifier" in text
    assert "## Sheet excerpt" in text
    assert "A3: IO-1" in text


def test_build_input_includes_alternative_candidates() -> None:
    alts = [_finding(canonical="style_code", col="B")]
    text = IdentifierFindingJudge().build_input(ctx=None, inputs=_inputs(alternative_candidates=alts))
    assert "## Alternative candidates" in text
    assert "style_code" in text
    assert "B3" in text


def test_build_input_omits_alternative_section_when_empty() -> None:
    text = IdentifierFindingJudge().build_input(ctx=None, inputs=_inputs())
    assert "## Alternative candidates" not in text


def test_build_input_includes_validator_warnings() -> None:
    w = ValidationWarning(name="missing_mandatory_io_number", severity="error",
                          message="row 3 missing io_number")
    text = IdentifierFindingJudge().build_input(ctx=None, inputs=_inputs(validator_warnings=[w]))
    assert "## Validator warnings" in text
    assert "[error] missing_mandatory_io_number" in text


def test_build_input_includes_cluster_context_when_set() -> None:
    text = IdentifierFindingJudge().build_input(ctx=None,
                                                  inputs=_inputs(cluster_context="cluster_id=c0 sheet=Plan"))
    assert "## Cluster context" in text
    assert "cluster_id=c0" in text


# ─── End-to-end with FakeLLM ─────────────────────────────────────────────


def test_keep_verdict_returns_validated_output() -> None:
    canned = {
        "IdentifierVerdict": {
            "decision": "keep",
            "alternative_coord": None,
            "reason": "header row matches IO NO",
            "confidence": "high",
        },
    }
    result = IdentifierFindingJudge().run(ctx=None, inputs=_inputs(), provider=FakeLLM(canned=canned))
    assert isinstance(result, IdentifierVerdict)
    assert result.decision == "keep"


def test_rewrite_verdict_with_coord_returns_validated_output() -> None:
    canned = {
        "IdentifierVerdict": {
            "decision": "rewrite",
            "alternative_coord": ["B", 3],
            "reason": "column B header reads STYLE NO",
            "confidence": "medium",
        },
    }
    result = IdentifierFindingJudge().run(ctx=None, inputs=_inputs(), provider=FakeLLM(canned=canned))
    assert isinstance(result, IdentifierVerdict)
    assert result.decision == "rewrite"
    assert result.alternative_coord == ("B", 3)


# ─── Retry path: semantic validator rejects, second attempt succeeds ─────


def test_rewrite_without_coord_triggers_retry_then_succeeds() -> None:
    bad  = {"decision": "rewrite", "alternative_coord": None,
            "reason": "x", "confidence": "medium"}
    good = {"decision": "rewrite", "alternative_coord": ["B", 3],
            "reason": "x", "confidence": "medium"}
    llm = FakeLLM(canned={}).script_responses(bad, good)
    result = IdentifierFindingJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, IdentifierVerdict)
    assert result.alternative_coord == ("B", 3)


def test_keep_with_coord_triggers_retry_then_succeeds() -> None:
    bad  = {"decision": "keep", "alternative_coord": ["B", 3],
            "reason": "x", "confidence": "high"}
    good = {"decision": "keep", "alternative_coord": None,
            "reason": "x", "confidence": "high"}
    llm = FakeLLM(canned={}).script_responses(bad, good)
    result = IdentifierFindingJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, IdentifierVerdict)
    assert result.decision == "keep"
    assert result.alternative_coord is None


def test_two_consecutive_semantic_failures_yield_run_failure() -> None:
    """Both responses violate the semantic invariant → AgentRunFailure."""
    bad1 = {"decision": "rewrite", "alternative_coord": None,
            "reason": "x", "confidence": "low"}
    bad2 = {"decision": "drop", "alternative_coord": ["B", 3],
            "reason": "x", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad1, bad2)
    result = IdentifierFindingJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, AgentRunFailure)


# ─── Class attributes ────────────────────────────────────────────────────


def test_agent_uses_identifier_finding_judge_prompt() -> None:
    from app.prompts import IDENTIFIER_FINDING_JUDGE
    assert IdentifierFindingJudge.prompt is IDENTIFIER_FINDING_JUDGE


def test_agent_output_schema_is_identifier_verdict() -> None:
    assert IdentifierFindingJudge.output_schema is IdentifierVerdict


def test_agent_name_used_for_telemetry_keys() -> None:
    assert IdentifierFindingJudge.name == "identifier_finding_judge"
