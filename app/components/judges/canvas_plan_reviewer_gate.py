"""CanvasPlanReviewerGate — routes assembled plans through CanvasPlanReviewer.

A pipeline-facing Haystack component that owns one
`CanvasPlanReviewerAgent` privately and decides per-plan whether to
invoke the reviewer. The pipeline never imports the agent directly —
it sees only this gate.

Triggers for invoking the reviewer:
  - the plan carries any ValidationWarning, OR
  - at least one winning FieldLocation scored below the agent's
    `tuning.min_winner_score`.

Reviewer verdict is applied as follows:
  - approve  → plan flows through unchanged
  - repick   → for each canonical repick, find a matching
                LocationCandidate in `plan.scoreboards[canonical]`
                with `mode + coord` equal to the verdict's. Replace
                that canonical's FieldLocation. Unmatched repicks
                attach a warning so no silent re-pick happens.
  - escalate → plan unchanged; reviewer's reason is attached as a
                ValidationWarning.

When the agent returns `AgentRunFailure`, the original plan flows
through with a warning — fail-safe: the LLM going down must not
silently mutate or drop data.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from haystack import component

from app.agents._base import AgentRunFailure
from app.agents.judges.canvas_plan_reviewer import (
    CanonicalRepick,
    CanvasPlanReviewerAgent,
    CanvasPlanReviewerInputs,
    PlanReviewVerdict,
)
from app.artifacts.finding import ValidationWarning
from app.artifacts.plan import (
    CanvasPlan,
    FieldLocation,
    LocationCandidate,
)
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.read_direction import ReadDirection
from app.inferencing._base import BaseProvider


_MODE_FROM_STR: dict[str, FieldLocationMode] = {
    "column":   FieldLocationMode.COLUMN,
    "row":      FieldLocationMode.ROW,
    "kv_block": FieldLocationMode.KV_BLOCK,
}


@component
class CanvasPlanReviewerGate(Component):
    """Route plans through CanvasPlanReviewer when warnings or low scores fire."""

    def __init__(self, llm: BaseProvider) -> None:
        Component.__init__(self)
        self._agent     = CanvasPlanReviewerAgent()
        self._llm       = llm
        self._threshold = self._agent.tuning.min_winner_score

    @component.output_types(plan=CanvasPlan)
    def run(self, plan: CanvasPlan, bundle: ClusterAnchorBundle) -> dict:
        if not self._should_review(plan):
            return {"plan": plan}

        inputs = CanvasPlanReviewerInputs(
            plan_summary=_render_plan_summary(plan),
            scoreboard_summary=_render_scoreboard_summary(plan),
            warnings=list(plan.warnings),
            cluster_context=(
                f"cluster_id={bundle.cluster.cluster_id} "
                f"sheet={bundle.anchor_sheet_name}"
            ),
        )
        verdict = self._agent.run(ctx=bundle, inputs=inputs, provider=self._llm)
        if isinstance(verdict, AgentRunFailure):
            self.log.warning("plan_reviewer_fallback",
                             cluster=bundle.cluster.cluster_id, reason=verdict.reason)
            return {"plan": _attach_warning(
                plan, name="plan_reviewer_failed", severity="warning",
                message=f"reviewer agent failed: {verdict.reason}",
            )}
        return {"plan": _apply_verdict(plan, verdict)}

    # ── trigger logic ────────────────────────────────────────────────────

    def _should_review(self, plan: CanvasPlan) -> bool:
        """Return True when validator warnings or low scores warrant review."""
        if plan.warnings:
            return True
        for fl in plan.field_locations.values():
            if fl.mode == FieldLocationMode.MISSING:
                continue
            if fl.score < self._threshold:
                return True
        return False


# ── verdict application ─────────────────────────────────────────────────


def _apply_verdict(plan: CanvasPlan, verdict: PlanReviewVerdict) -> CanvasPlan:
    """Apply approve / repick / escalate to the plan; return the result."""
    if verdict.decision == "approve":
        return plan
    if verdict.decision == "escalate":
        return _attach_warning(
            plan, name="plan_reviewer_escalated", severity="warning",
            message=f"reviewer escalated: {verdict.reason}",
        )

    new_field_locations = dict(plan.field_locations)
    new_warnings        = list(plan.warnings)
    for repick in verdict.repicks:
        candidate, score = _match_repick_to_scoreboard(plan, repick)
        if candidate is None:
            new_warnings.append(ValidationWarning(
                name="plan_reviewer_unmatched_repick",
                severity="warning",
                message=(
                    f"reviewer repick for '{repick.canonical}' "
                    f"didn't match any scoreboard candidate"
                ),
            ))
            continue
        new_field_locations[repick.canonical] = _location_from_candidate(
            canonical=repick.canonical, candidate=candidate, score=score,
        )
    return replace(
        plan,
        field_locations=new_field_locations,
        warnings=new_warnings,
    )


def _match_repick_to_scoreboard(
    plan:   CanvasPlan,
    repick: CanonicalRepick,
) -> tuple[LocationCandidate | None, float]:
    """Find the scoreboard candidate whose (mode, coord) matches a repick."""
    scoreboard = plan.scoreboards.get(repick.canonical, [])
    target_mode = _MODE_FROM_STR.get(repick.mode)
    if target_mode is None:
        return None, 0.0
    for candidate, score, eliminated in scoreboard:
        if candidate.mode != target_mode:
            continue
        if _candidate_coord_matches(candidate, repick):
            return candidate, score
    _ = eliminated  # the gate trusts the reviewer; elimination is advisory.
    return None, 0.0


def _candidate_coord_matches(
    candidate: LocationCandidate,
    repick:    CanonicalRepick,
) -> bool:
    """True when the candidate's coord slot equals the repick's."""
    if repick.mode == "column":
        return candidate.column == repick.column
    if repick.mode == "row":
        return candidate.row == repick.row
    if repick.mode == "kv_block":
        if candidate.kv_block is None or repick.kv_label_coord is None:
            return False
        return candidate.kv_block.label_coord == repick.kv_label_coord
    return False


def _location_from_candidate(
    *,
    canonical: str,
    candidate: LocationCandidate,
    score:     float,
) -> FieldLocation:
    """Build a FieldLocation from a winning candidate after a repick."""
    if candidate.mode == FieldLocationMode.COLUMN:
        return FieldLocation(
            canonical=canonical,
            mode=FieldLocationMode.COLUMN,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_ROW,
            column=candidate.column, score=score,
        )
    if candidate.mode == FieldLocationMode.ROW:
        return FieldLocation(
            canonical=canonical,
            mode=FieldLocationMode.ROW,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_COLUMN,
            row=candidate.row, score=score,
        )
    if candidate.mode == FieldLocationMode.KV_BLOCK:
        return FieldLocation(
            canonical=canonical,
            mode=FieldLocationMode.KV_BLOCK,
            scope=FieldScope.SHEET,
            read_direction=ReadDirection.FIXED,
            kv_block=candidate.kv_block, score=score,
        )
    return FieldLocation(
        canonical=canonical,
        mode=FieldLocationMode.MISSING,
        scope=FieldScope.PLI,
        read_direction=ReadDirection.SAME_ROW,
    )


def _attach_warning(
    plan: CanvasPlan, *, name: str, severity: str, message: str,
) -> CanvasPlan:
    return replace(
        plan, warnings=[*plan.warnings, ValidationWarning(
            name=name, severity=severity, message=message,
        )],
    )


# ── prompt-ready rendering ──────────────────────────────────────────────


def _render_plan_summary(plan: CanvasPlan) -> str:
    """One-block dump of plan identity + winners + stages + metadata."""
    lines = [
        f"cluster_id={plan.cluster_id} sheet={plan.anchor_sheet_name}",
        f"pli_axis={plan.pli_axis.value} pli_rows={plan.pli_rows}",
        "field_locations:",
    ]
    for canonical, fl in plan.field_locations.items():
        lines.append(f"  - {canonical}: {_render_location(fl)} (score={fl.score:.2f})")
    if plan.stage_bands:
        lines.append("stage_bands:")
        for b in plan.stage_bands:
            lines.append(
                f"  - {b.name!r} at {b.anchor_coord} subfield_axis={b.subfield_axis.value}"
            )
    if plan.metadata_entries:
        lines.append("metadata:")
        for m in plan.metadata_entries:
            lines.append(f"  - {m.header_text!r} ({m.mode.value})")
    return "\n".join(lines)


def _render_location(fl: FieldLocation) -> str:
    if fl.mode == FieldLocationMode.COLUMN:
        return f"COLUMN col={fl.column}"
    if fl.mode == FieldLocationMode.ROW:
        return f"ROW row={fl.row}"
    if fl.mode == FieldLocationMode.KV_BLOCK and fl.kv_block is not None:
        return f"KV_BLOCK label={fl.kv_block.label_coord}"
    return "MISSING"


def _render_scoreboard_summary(plan: CanvasPlan) -> str:
    """Per-canonical candidate list with scores + elimination flag."""
    if not plan.scoreboards:
        return ""
    lines: list[str] = []
    for canonical, scoreboard in plan.scoreboards.items():
        if not scoreboard:
            continue
        lines.append(f"{canonical}:")
        for candidate, score, eliminated in scoreboard:
            tag = "ELIM" if eliminated else "    "
            lines.append(
                f"  [{tag}] score={score:.2f} mode={candidate.mode.value} "
                f"column={candidate.column} row={candidate.row} "
                f"kv={candidate.kv_block.label_coord if candidate.kv_block else None}"
            )
    return "\n".join(lines)
