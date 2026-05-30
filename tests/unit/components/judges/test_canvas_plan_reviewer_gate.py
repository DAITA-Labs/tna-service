"""CanvasPlanReviewerGate — review-trigger + verdict-apply behaviour."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.finding import ValidationWarning
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.plan import (
    CanvasPlan,
    FieldLocation,
    LocationCandidate,
)
from app.artifacts.structure import KvBlock, StructureBag
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.judges.canvas_plan_reviewer_gate import CanvasPlanReviewerGate
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.pli_axis import PliAxis
from app.enums.read_direction import ReadDirection
from tests.fixtures.fake_llm import FakeLLM


# ── Fixture helpers ────────────────────────────────────────────────────────


def _bundle() -> ClusterAnchorBundle:
    canvas = GridCanvas(
        n_rows=10, n_cols=10,
        cell_values=[[None] * 10 for _ in range(10)],
        channels={},
    )
    bag = StructureBag()
    hint = LayoutHint(
        axes=LayoutAxes(
            pli_axis="vertical", stage_axis="horizontal", subfield_axis="horizontal",
            confidence={"pli": 0.9, "stage": 0.9, "subfield": 0.9},
        ),
        cluster_id="c0", confidence=0.9,
        candidate_columns={}, candidate_rows={}, candidate_kv_blocks={},
        data_row_ranges=[], section_boundaries=[], header_band=None,
    )
    cluster = PliCluster(cluster_id="c0", sheet_names=["TNA"])
    return ClusterAnchorBundle(
        cluster=cluster, anchor_sheet_name="TNA",
        canvas=canvas, bag=bag, hint=hint,
    )


def _plan(
    *,
    field_locations: dict[str, FieldLocation] | None = None,
    warnings:        list[ValidationWarning] | None = None,
    scoreboards:     dict | None = None,
) -> CanvasPlan:
    return CanvasPlan(
        cluster_id="c0", anchor_sheet_name="TNA",
        pli_axis=PliAxis.ROW,
        field_locations=field_locations or {},
        warnings=warnings or [],
        scoreboards=scoreboards or {},
    )


def _column_winner(canonical: str, column: int, score: float = 0.9) -> FieldLocation:
    return FieldLocation(
        canonical=canonical, mode=FieldLocationMode.COLUMN,
        scope=FieldScope.PLI, read_direction=ReadDirection.SAME_ROW,
        column=column, score=score,
    )


def _approve() -> dict:
    return {"decision": "approve", "reason": "looks correct", "confidence": "high"}


def _escalate() -> dict:
    return {"decision": "escalate",
             "reason": "evidence ambiguous", "confidence": "low"}


def _repick(canonical: str, *, column: int = 3) -> dict:
    return {
        "decision": "repick",
        "repicks": [{"canonical": canonical, "mode": "column", "column": column}],
        "reason": f"{canonical} should be at column {column}",
        "confidence": "medium",
    }


# ── Trigger gating ─────────────────────────────────────────────────────────


def test_no_warnings_and_all_high_scores_skip_judge() -> None:
    """Plan with no warnings + all scores above threshold → judge not invoked."""
    plan = _plan(
        field_locations={"io_number": _column_winner("io_number", 2, score=0.92)},
    )
    gate = CanvasPlanReviewerGate(llm=FakeLLM(canned={}))
    out  = gate.run(plan=plan, bundle=_bundle())
    assert out["plan"] is plan


def test_warning_on_plan_triggers_judge() -> None:
    plan = _plan(
        field_locations={"io_number": _column_winner("io_number", 2, score=0.92)},
        warnings=[ValidationWarning(
            name="mandatory_missing_quantity", severity="warning",
            message="quantity not located",
        )],
    )
    gate = CanvasPlanReviewerGate(llm=FakeLLM(canned={"PlanReviewVerdict": _approve()}))
    out  = gate.run(plan=plan, bundle=_bundle())
    # Approve flows through unchanged.
    assert out["plan"] is plan


def test_low_winner_score_triggers_judge() -> None:
    """A winning location below tuning.min_winner_score (0.6) triggers review."""
    plan = _plan(
        field_locations={"io_number": _column_winner("io_number", 2, score=0.4)},
    )
    gate = CanvasPlanReviewerGate(llm=FakeLLM(canned={"PlanReviewVerdict": _approve()}))
    out  = gate.run(plan=plan, bundle=_bundle())
    assert out["plan"] is plan


def test_missing_winner_does_not_trigger_judge() -> None:
    """A canonical marked MISSING does NOT trigger review on its own."""
    plan = _plan(
        field_locations={"io_number": FieldLocation(
            canonical="io_number", mode=FieldLocationMode.MISSING,
            scope=FieldScope.PLI, read_direction=ReadDirection.SAME_ROW,
            score=0.0,
        )},
    )
    gate = CanvasPlanReviewerGate(llm=FakeLLM(canned={}))
    out  = gate.run(plan=plan, bundle=_bundle())
    assert out["plan"] is plan


# ── Verdict application ────────────────────────────────────────────────────


def test_escalate_attaches_warning_and_preserves_locations() -> None:
    plan = _plan(
        field_locations={"io_number": _column_winner("io_number", 2, score=0.4)},
    )
    gate = CanvasPlanReviewerGate(llm=FakeLLM(canned={"PlanReviewVerdict": _escalate()}))
    out  = gate.run(plan=plan, bundle=_bundle())
    new_plan = out["plan"]
    names = {w.name for w in new_plan.warnings}
    assert "plan_reviewer_escalated" in names
    assert new_plan.field_locations == plan.field_locations


def test_repick_swaps_to_matching_scoreboard_candidate() -> None:
    scoreboards = {"io_number": [
        (LocationCandidate(mode=FieldLocationMode.COLUMN, column=2), 0.4, False),
        (LocationCandidate(mode=FieldLocationMode.COLUMN, column=3), 0.65, False),
    ]}
    plan = _plan(
        field_locations={"io_number": _column_winner("io_number", 2, score=0.4)},
        scoreboards=scoreboards,
    )
    gate = CanvasPlanReviewerGate(llm=FakeLLM(
        canned={"PlanReviewVerdict": _repick("io_number", column=3)}
    ))
    out      = gate.run(plan=plan, bundle=_bundle())
    new_fl   = out["plan"].field_locations["io_number"]
    assert new_fl.column == 3
    assert new_fl.score  == 0.65
    # No "unmatched repick" warning.
    assert not any(w.name == "plan_reviewer_unmatched_repick" for w in out["plan"].warnings)


def test_repick_with_no_matching_candidate_emits_warning() -> None:
    """Reviewer proposing a candidate the scoreboard doesn't contain → warning, plan unchanged."""
    scoreboards = {"io_number": [
        (LocationCandidate(mode=FieldLocationMode.COLUMN, column=2), 0.4, False),
    ]}
    plan = _plan(
        field_locations={"io_number": _column_winner("io_number", 2, score=0.4)},
        scoreboards=scoreboards,
    )
    gate = CanvasPlanReviewerGate(llm=FakeLLM(
        canned={"PlanReviewVerdict": _repick("io_number", column=99)}
    ))
    out = gate.run(plan=plan, bundle=_bundle())
    assert any(w.name == "plan_reviewer_unmatched_repick" for w in out["plan"].warnings)
    # Winner location preserved.
    assert out["plan"].field_locations["io_number"].column == 2


def test_repick_kv_block_mode_matches_via_label_coord() -> None:
    kv = KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                  label_text="Style", value_dtype=4)
    scoreboards = {"style_code": [
        (LocationCandidate(mode=FieldLocationMode.KV_BLOCK, kv_block=kv), 0.8, False),
    ]}
    plan = _plan(
        field_locations={"style_code": _column_winner("style_code", 5, score=0.45)},
        scoreboards=scoreboards,
    )
    gate = CanvasPlanReviewerGate(llm=FakeLLM(
        canned={"PlanReviewVerdict": {
            "decision": "repick",
            "repicks": [{
                "canonical": "style_code", "mode": "kv_block",
                "kv_label_coord": ["A", 2],
            }],
            "reason": "style_code is the Style: A2/B2 KV pair",
            "confidence": "high",
        }}
    ))
    out    = gate.run(plan=plan, bundle=_bundle())
    new_fl = out["plan"].field_locations["style_code"]
    assert new_fl.mode     == FieldLocationMode.KV_BLOCK
    assert new_fl.kv_block is kv


# ── Failure path ───────────────────────────────────────────────────────────


def test_agent_failure_preserves_plan_and_attaches_warning() -> None:
    """When the agent returns AgentRunFailure, the plan flows through with a warning."""
    plan = _plan(
        field_locations={"io_number": _column_winner("io_number", 2, score=0.4)},
    )
    # FakeLLM with no canned response → AssertionError inside the agent →
    # the Agent base catches and returns AgentRunFailure after retries exhaust.
    gate = CanvasPlanReviewerGate(llm=FakeLLM(canned={}))
    out  = gate.run(plan=plan, bundle=_bundle())
    new_plan = out["plan"]
    assert any(w.name == "plan_reviewer_failed" for w in new_plan.warnings)
    # field_locations preserved.
    assert new_plan.field_locations["io_number"].column == 2
