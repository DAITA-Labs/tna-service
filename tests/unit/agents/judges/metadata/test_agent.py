"""MetadataFindingJudge build_input + retry behaviour with FakeLLM."""
from __future__ import annotations

from app.agents._base import AgentRunFailure
from app.agents.judges.metadata import MetadataFindingJudge
from app.agents.judges.metadata.schema import (
    MetadataFindingForJudge,
    MetadataVerdict,
)
from app.specs.schemas import MetadataEntry
from tests.fixtures.fake_llm import FakeLLM


def _entry(**overrides) -> MetadataEntry:
    base = dict(key="Treatment", value="Garment Dye", source="K4", canonical=None)
    base.update(overrides)
    return MetadataEntry(**base)


def _inputs(**overrides) -> MetadataFindingForJudge:
    base = dict(
        metadata=_entry(),
        metadata_catalog="- buyer — aliases: buyer, customer, brand",
        sheet_excerpt="...",
    )
    base.update(overrides)
    return MetadataFindingForJudge(**base)


# ─── build_input ─────────────────────────────────────────────────────────


def test_build_input_includes_entry_and_catalog() -> None:
    text = MetadataFindingJudge().build_input(ctx=None, inputs=_inputs())
    assert "## Metadata entry under review" in text
    assert "Treatment" in text
    assert "Garment Dye" in text
    assert "## Metadata catalog" in text


def test_build_input_includes_cluster_context_when_set() -> None:
    text = MetadataFindingJudge().build_input(
        ctx=None, inputs=_inputs(cluster_context="cluster_id=c0 sheet=Plan"),
    )
    assert "## Cluster context" in text


# ─── End-to-end with FakeLLM ─────────────────────────────────────────────


def test_keep_verdict_returns_validated_output() -> None:
    canned = {"MetadataVerdict": {
        "decision": "keep", "alternative_canonical": None,
        "reason": "novel label, open-vocab", "confidence": "medium",
    }}
    result = MetadataFindingJudge().run(ctx=None, inputs=_inputs(), provider=FakeLLM(canned=canned))
    assert isinstance(result, MetadataVerdict)
    assert result.decision == "keep"


def test_rewrite_verdict_with_valid_canonical_returns_output() -> None:
    canned = {"MetadataVerdict": {
        "decision": "rewrite", "alternative_canonical": "buyer",
        "reason": "key 'Buyer Name' matches buyer alias", "confidence": "high",
    }}
    inputs = _inputs(metadata=_entry(key="Buyer Name", value="Nike"))
    result = MetadataFindingJudge().run(ctx=None, inputs=inputs, provider=FakeLLM(canned=canned))
    assert isinstance(result, MetadataVerdict)
    assert result.alternative_canonical == "buyer"


def test_hallucinated_canonical_triggers_retry_then_succeeds() -> None:
    bad  = {"decision": "rewrite", "alternative_canonical": "imaginary_canonical",
            "reason": "x", "confidence": "high"}
    good = {"decision": "rewrite", "alternative_canonical": "buyer",
            "reason": "x", "confidence": "high"}
    llm = FakeLLM(canned={}).script_responses(bad, good)
    result = MetadataFindingJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, MetadataVerdict)
    assert result.alternative_canonical == "buyer"


def test_two_invalid_canonicals_yield_agent_run_failure() -> None:
    bad = {"decision": "rewrite", "alternative_canonical": "fake",
            "reason": "x", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad, bad)
    result = MetadataFindingJudge().run(ctx=None, inputs=_inputs(), provider=llm)
    assert isinstance(result, AgentRunFailure)


# ─── Class attributes ────────────────────────────────────────────────────


def test_agent_uses_metadata_finding_judge_prompt() -> None:
    from app.prompts import METADATA_FINDING_JUDGE
    assert MetadataFindingJudge.prompt is METADATA_FINDING_JUDGE


def test_agent_name_used_for_telemetry_keys() -> None:
    assert MetadataFindingJudge.name == "metadata_finding_judge"
