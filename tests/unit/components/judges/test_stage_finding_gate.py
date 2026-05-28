"""StageFindingGate — routes novel-canonical FinalStages to the judge."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.components.judges.stage_finding_gate import (
    StageFindingGate,
    _apply_verdict,
    _is_novel,
    _render_stage_catalog,
)
from app.agents.judges.stage_finding.schema import StageFindingAudit, StageVerdict
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


def _verdict(decision: str, alt: str | None = None) -> dict:
    return {"decision": decision, "alternative_canonical": alt,
            "reason": "test reason", "confidence": "high"}


# ─── Short-circuit paths ─────────────────────────────────────────────────


def test_no_stages_returns_empty() -> None:
    gate = StageFindingGate(llm=FakeLLM(canned={}))
    out = gate.run(stages_per_row={}, bundle=_bundle())
    assert out["stages_per_row"] == {}


def test_stage_with_canonical_set_passes_through() -> None:
    """No judge call when canonical is already resolved."""
    gate = StageFindingGate(llm=FakeLLM(canned={}))
    stages = {3: [_stage(canonical="fabric")]}
    out = gate.run(stages_per_row=stages, bundle=_bundle())
    assert out["stages_per_row"] == stages


def test_stage_with_blank_name_skipped() -> None:
    """An empty `name` field isn't routed (no signal for the judge)."""
    gate = StageFindingGate(llm=FakeLLM(canned={}))
    stages = {3: [_stage(name="")]}
    out = gate.run(stages_per_row=stages, bundle=_bundle())
    assert out["stages_per_row"][3] == stages[3]


# ─── Verdict application ─────────────────────────────────────────────────


def test_keep_verdict_preserves_stage() -> None:
    llm = FakeLLM(canned={"StageVerdict": _verdict("keep")})
    gate = StageFindingGate(llm=llm)
    out = gate.run(stages_per_row={3: [_stage()]}, bundle=_bundle())
    assert len(out["stages_per_row"][3]) == 1
    assert out["stages_per_row"][3][0].canonical is None


def test_drop_verdict_removes_stage() -> None:
    llm = FakeLLM(canned={"StageVerdict": _verdict("drop")})
    gate = StageFindingGate(llm=llm)
    out = gate.run(stages_per_row={3: [_stage()]}, bundle=_bundle())
    assert out["stages_per_row"][3] == []


def test_rewrite_verdict_sets_canonical_and_judge_action() -> None:
    llm = FakeLLM(canned={"StageVerdict": _verdict("rewrite", alt="fabric")})
    gate = StageFindingGate(llm=llm)
    out = gate.run(stages_per_row={3: [_stage()]}, bundle=_bundle())
    adjudicated = out["stages_per_row"][3][0]
    assert adjudicated.canonical == "fabric"
    assert adjudicated.judge_action == "canonical_set_to_fabric"


def test_agent_failure_keeps_stage() -> None:
    """Two invalid LLM responses → AgentRunFailure → stage retained."""
    bad = {"decision": "rewrite", "alternative_canonical": "made_up",
            "reason": "x", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad, bad)
    gate = StageFindingGate(llm=llm)
    original = _stage()
    out = gate.run(stages_per_row={3: [original]}, bundle=_bundle())
    assert out["stages_per_row"][3] == [original]


# ─── Mixed input ─────────────────────────────────────────────────────────


def test_mix_of_canonical_and_novel_routes_only_novel() -> None:
    llm = FakeLLM(canned={"StageVerdict": _verdict("keep")})
    gate = StageFindingGate(llm=llm)
    stages = {3: [
        _stage(name="Fabric",        canonical="fabric"),    # already resolved
        _stage(name="Sample Inspect", canonical=None),       # novel → judge fires
    ]}
    out = gate.run(stages_per_row=stages, bundle=_bundle())
    assert len(out["stages_per_row"][3]) == 2
    assert out["stages_per_row"][3][0].canonical == "fabric"
    assert out["stages_per_row"][3][1].canonical is None    # kept by judge


def test_multiple_rows_each_processed() -> None:
    llm = FakeLLM(canned={"StageVerdict": _verdict("keep")})
    gate = StageFindingGate(llm=llm)
    stages = {3: [_stage()], 7: [_stage()]}
    out = gate.run(stages_per_row=stages, bundle=_bundle())
    assert set(out["stages_per_row"]) == {3, 7}


# ─── Helpers ─────────────────────────────────────────────────────────────


def test_is_novel_true_for_no_canonical_with_name() -> None:
    assert _is_novel(_stage(canonical=None, name="something"))


def test_is_novel_false_when_canonical_set() -> None:
    assert not _is_novel(_stage(canonical="fabric"))


def test_is_novel_false_for_blank_name() -> None:
    assert not _is_novel(_stage(canonical=None, name=""))
    assert not _is_novel(_stage(canonical=None, name="   "))


def test_apply_verdict_keep_returns_same() -> None:
    s = _stage()
    v = StageVerdict(decision="keep", reason="x", confidence="high")
    assert _apply_verdict(s, v) is s


def test_apply_verdict_drop_returns_none() -> None:
    v = StageVerdict(decision="drop", reason="x", confidence="medium")
    assert _apply_verdict(_stage(), v) is None


def test_apply_verdict_rewrite_updates_canonical_and_action() -> None:
    v = StageVerdict(decision="rewrite", alternative_canonical="cutting",
                      reason="x", confidence="high")
    new = _apply_verdict(_stage(), v)
    assert new is not None
    assert new.canonical == "cutting"
    assert new.judge_action == "canonical_set_to_cutting"


def test_render_stage_catalog_lists_known_canonicals() -> None:
    text = _render_stage_catalog()
    assert "fabric" in text
    assert "cutting" in text
    assert "aliases:" in text


# ─── Audit output socket ────────────────────────────────────────────────


def test_audits_empty_when_no_stages() -> None:
    gate = StageFindingGate(llm=FakeLLM(canned={}))
    out = gate.run(stages_per_row={}, bundle=_bundle())
    assert out["audits"] == []


def test_audits_empty_when_nothing_novel() -> None:
    gate = StageFindingGate(llm=FakeLLM(canned={}))
    out = gate.run(stages_per_row={3: [_stage(canonical="fabric")]}, bundle=_bundle())
    assert out["audits"] == []


def test_audit_carries_verdict_with_row_and_index() -> None:
    llm = FakeLLM(canned={"StageVerdict": _verdict("rewrite", alt="fabric")})
    gate = StageFindingGate(llm=llm)
    stages = {3: [_stage(canonical="cutting"),    # idx 0, clean
                  _stage(name="Sample Inspect", canonical=None)]}   # idx 1, judged
    out = gate.run(stages_per_row=stages, bundle=_bundle())
    assert len(out["audits"]) == 1
    audit = out["audits"][0]
    assert isinstance(audit, StageFindingAudit)
    assert audit.row == 3
    assert audit.stage_index == 1
    assert audit.verdict is not None
    assert audit.verdict.alternative_canonical == "fabric"
    assert audit.judge_failed is False


def test_audit_marks_judge_failed_on_agent_run_failure() -> None:
    bad = {"decision": "rewrite", "alternative_canonical": "made_up",
            "reason": "x", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad, bad)
    gate = StageFindingGate(llm=llm)
    out = gate.run(stages_per_row={3: [_stage()]}, bundle=_bundle())
    assert len(out["audits"]) == 1
    assert out["audits"][0].verdict is None
    assert out["audits"][0].judge_failed is True


# ─── Component plumbing ─────────────────────────────────────────────────


def test_gate_sockets_registered() -> None:
    gate = StageFindingGate(llm=FakeLLM(canned={}))
    assert "stages_per_row" in gate.__haystack_input__._sockets_dict
    assert "bundle" in gate.__haystack_input__._sockets_dict
    outputs = gate.__haystack_output__._sockets_dict
    assert "stages_per_row" in outputs
    assert "audits" in outputs


def test_gate_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("stage_judge", StageFindingGate(llm=FakeLLM(canned={})))
    assert "stage_judge" in pipeline.graph.nodes
