"""IdentifierPhaseGate — bag-level arbiter for identifier findings.

Runs AFTER `IdentifierFindingGate` and reads two parallel inputs:
the raw findings (pre per-finding judging) and the audits that
per-finding judging emitted. The phase judge sees both plus the
residual warnings and emits decisions that override per-finding.

Trigger: invoke the LLM only when there's residual signal worth
arbitrating — any warning still in `warnings`, OR any audit with
`judge_failed=True`. Otherwise the gate is a pass-through that
returns the post-per-finding bag (constructed from raw + audits).

Decisions apply via the same `_apply_verdict` semantics as the
per-finding gate (keep / drop / rewrite), but driven by
`IdentifierPhaseVerdict.decisions` which carry a `finding_index`
into the raw findings list.

AgentRunFailure on the phase judge → return the post-per-finding bag
unchanged (the per-finding outcomes win by default).
"""
from __future__ import annotations

from haystack import component
from openpyxl.utils import column_index_from_string

from app.agents._base import AgentRunFailure
from app.agents.judges.identifier_finding.schema import (
    IdentifierFindingAudit,
    IdentifierVerdict,
)
from app.agents.judges.identifier_phase import IdentifierPhaseJudge
from app.agents.judges.identifier_phase.schema import (
    FindingDecision,
    IdentifierPhaseForJudge,
)
from app.artifacts.canvas import GridCanvas
from app.artifacts.finding import Confidence, Finding, ValidationWarning
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.inferencing._base import BaseProvider
from app.specs.identifiers import IDENTIFIER_SPECS, get_identifier_spec


_VERDICT_CONF_TO_FINDING_CONF: dict[str, Confidence] = {
    "high":   Confidence.HIGH,
    "medium": Confidence.MEDIUM,
    "low":    Confidence.LOW,
}


@component
class IdentifierPhaseGate(Component):
    """Run IdentifierPhaseJudge when residual warnings or per-finding failures remain."""

    def __init__(self, llm: BaseProvider) -> None:
        Component.__init__(self)
        self._agent = IdentifierPhaseJudge()
        self._llm = llm

    @component.output_types(findings=list[Finding])
    def run(
        self,
        raw_findings: list[Finding],
        audits:       list[IdentifierFindingAudit],
        warnings:     list[ValidationWarning],
        bundle:       ClusterAnchorBundle,
    ) -> dict:
        post_finding = _apply_audits(raw_findings, audits, bundle.canvas)
        if not _should_invoke(warnings, audits):
            return {"findings": post_finding}

        inputs = IdentifierPhaseForJudge(
            raw_findings=raw_findings,
            audits=audits,
            warnings=warnings,
            pli_rows=_pli_rows(bundle),
            spec_snippets=_collect_spec_snippets(raw_findings),
            sheet_summary=(
                f"cluster_id={bundle.cluster.cluster_id} sheet={bundle.anchor_sheet_name}"
            ),
        )
        verdict = self._agent.run(ctx=bundle, inputs=inputs, provider=self._llm)
        if isinstance(verdict, AgentRunFailure):
            self.log.warning("phase_judge_fallback_kept_bag",
                              phase="identifier", reason=verdict.reason)
            return {"findings": post_finding}
        return {"findings": _apply_phase_decisions(raw_findings, verdict.decisions,
                                                     post_finding, bundle.canvas)}


# ── module-level pure helpers ───────────────────────────────────────────


def _should_invoke(
    warnings: list[ValidationWarning],
    audits:   list[IdentifierFindingAudit],
) -> bool:
    """The phase judge fires when there's residual signal worth arbitrating."""
    if warnings:
        return True
    return any(a.judge_failed for a in audits)


def _apply_audits(
    raw_findings: list[Finding],
    audits:       list[IdentifierFindingAudit],
    canvas:       GridCanvas,
) -> list[Finding]:
    """Reconstruct the post-per-finding bag from raw + audits.

    Used both as the gate's pass-through output when no LLM is invoked
    and as the starting point that the phase judge's decisions override.
    """
    verdict_by_index = {a.finding_index: a for a in audits}
    out: list[Finding] = []
    for idx, finding in enumerate(raw_findings):
        audit = verdict_by_index.get(idx)
        if audit is None:
            out.append(finding)
            continue
        if audit.judge_failed or audit.verdict is None:
            out.append(finding)
            continue
        adjudicated = _apply_single_verdict(finding, audit.verdict, canvas)
        if adjudicated is not None:
            out.append(adjudicated)
    return out


def _apply_phase_decisions(
    raw_findings: list[Finding],
    decisions:    list[FindingDecision],
    post_finding: list[Finding],
    canvas:       GridCanvas,
) -> list[Finding]:
    """Override post-per-finding outcomes with the phase judge's decisions."""
    decision_by_index = {d.finding_index: d for d in decisions}
    post_by_value_coord = {f.value_coord: f for f in post_finding}

    out: list[Finding] = []
    for idx, finding in enumerate(raw_findings):
        decision = decision_by_index.get(idx)
        if decision is None:
            # No phase override → use the post-per-finding result, if any.
            kept = post_by_value_coord.get(finding.value_coord)
            if kept is not None:
                out.append(kept)
            continue
        if decision.decision == "drop":
            continue
        if decision.decision == "keep":
            out.append(finding)
            continue
        # rewrite
        col_letter, row = decision.alternative_coord  # type: ignore[misc]
        col = column_index_from_string(col_letter)
        new_value = canvas.cell_values[row - 1][col - 1] if (
            1 <= row <= canvas.n_rows and 1 <= col <= canvas.n_cols
        ) else None
        out.append(Finding(
            canonical=finding.canonical,
            label_coord=finding.label_coord,
            value_coord=decision.alternative_coord,
            value=new_value,
            confidence=Confidence.HIGH,    # phase judge overrides imply high signal
            evidence=[*finding.evidence, "phase_judge_rewrite"],
        ))
    return out


def _apply_single_verdict(
    finding: Finding,
    verdict: IdentifierVerdict,
    canvas:  GridCanvas,
) -> Finding | None:
    """Apply one IdentifierVerdict (mirror of identifier_finding_gate._apply_verdict)."""
    if verdict.decision == "drop":
        return None
    if verdict.decision == "keep":
        return finding
    col_letter, row = verdict.alternative_coord  # type: ignore[misc]
    col = column_index_from_string(col_letter)
    new_value = canvas.cell_values[row - 1][col - 1] if (
        1 <= row <= canvas.n_rows and 1 <= col <= canvas.n_cols
    ) else None
    return Finding(
        canonical=finding.canonical,
        label_coord=finding.label_coord,
        value_coord=verdict.alternative_coord,
        value=new_value,
        confidence=_VERDICT_CONF_TO_FINDING_CONF[verdict.confidence],
        evidence=[*finding.evidence, "judge_rewrite"],
    )


def _pli_rows(bundle: ClusterAnchorBundle) -> list[int]:
    """Flatten DataRowRanges from the hint into a sorted list of 1-indexed rows."""
    rows: set[int] = set()
    for rng in bundle.hint.data_row_ranges:
        rows.update(range(rng.row_start, rng.row_end + 1))
    return sorted(rows)


def _collect_spec_snippets(findings: list[Finding]) -> dict[str, str]:
    """Render spec snippets for every catalogued canonical present in the bag."""
    snippets: dict[str, str] = {}
    for finding in findings:
        canonical = finding.canonical
        if canonical in snippets:
            continue
        try:
            spec = get_identifier_spec(canonical)
        except KeyError:
            continue
        lines = [spec.description]
        if spec.patterns:
            lines.append("Patterns: " + "; ".join(spec.patterns))
        if spec.anti_patterns:
            lines.append("Anti-patterns: " + "; ".join(spec.anti_patterns))
        snippets[canonical] = "\n".join(lines)
    return snippets
