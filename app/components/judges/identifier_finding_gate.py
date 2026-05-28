"""IdentifierFindingGate — routes ambiguous identifier findings to the judge.

A pipeline-facing Haystack component that owns one `IdentifierFindingJudge`
agent privately and decides per-finding whether to invoke the judge. The
pipeline never imports the agent directly — it sees only this gate.

Triggers for invoking the judge on a finding:
  - the finding's confidence falls below the agent's
    `tuning.confidence_threshold`, OR
  - any ValidationWarning's `affects_findings` includes the finding.

The judge's verdict (keep / drop / rewrite) is applied to the surrounding
findings list:
  - keep    → original finding flows through unchanged
  - drop    → finding is removed
  - rewrite → finding is replaced by a new Finding at `alternative_coord`
              with the value read from `bundle.canvas`; evidence carries
              a `judge_rewrite` tag; confidence inherits the judge's
              stated verdict confidence.

When the judge returns `AgentRunFailure`, the finding flows through
unchanged — fail-safe: the LLM going down must not silently delete data.

Findings whose canonical isn't in `IDENTIFIER_SPECS` pass through
without judge invocation (the judge's prompt is identifier-specific).
"""
from __future__ import annotations

from typing import Any

from haystack import component
from openpyxl.utils import column_index_from_string, get_column_letter

from app.agents._base import AgentRunFailure
from app.agents.judges.identifier_finding import IdentifierFindingJudge
from app.agents.judges.identifier_finding.schema import (
    FindingForJudge,
    IdentifierVerdict,
)
from app.artifacts.canvas import GridCanvas
from app.artifacts.finding import Confidence, Finding, ValidationWarning
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.inferencing._base import BaseProvider
from app.specs.identifiers import IDENTIFIER_SPECS, get_identifier_spec


# Numeric scores for the Confidence enum so the float threshold from
# tuning can be compared directly. The boundaries are chosen so the
# default threshold (0.7) routes MEDIUM and LOW findings to the judge
# while letting HIGH ones pass.
_CONFIDENCE_SCORE: dict[Confidence, float] = {
    Confidence.HIGH:   1.0,
    Confidence.MEDIUM: 0.5,
    Confidence.LOW:    0.2,
}

# Map the judge's self-reported confidence onto the Finding ladder so
# rewrites flow through with the judge's stated certainty rather than
# a hardcoded default.
_VERDICT_CONF_TO_FINDING_CONF: dict[str, Confidence] = {
    "high":   Confidence.HIGH,
    "medium": Confidence.MEDIUM,
    "low":    Confidence.LOW,
}

_IDENTIFIER_CANONICALS: frozenset[str] = frozenset(
    spec.canonical for spec in IDENTIFIER_SPECS
)


@component
class IdentifierFindingGate(Component):
    """Route ambiguous identifier findings through IdentifierFindingJudge."""

    def __init__(self, llm: BaseProvider) -> None:
        Component.__init__(self)
        self._agent = IdentifierFindingJudge()
        self._llm = llm
        self._threshold: float = self._agent.tuning.confidence_threshold

    @component.output_types(findings=list[Finding])
    def run(
        self,
        findings: list[Finding],
        warnings: list[ValidationWarning],
        bundle: ClusterAnchorBundle,
    ) -> dict:
        if not findings:
            return {"findings": []}

        ambiguous_ids = self._ambiguous_indices(findings, warnings)
        if not ambiguous_ids:
            return {"findings": findings}

        out: list[Finding] = []
        for idx, finding in enumerate(findings):
            if idx not in ambiguous_ids:
                out.append(finding)
                continue
            adjudicated = self._judge_one(finding, findings, warnings, bundle)
            if adjudicated is not None:
                out.append(adjudicated)
        return {"findings": out}

    # ── private helpers ──────────────────────────────────────────────────

    def _ambiguous_indices(
        self,
        findings: list[Finding],
        warnings: list[ValidationWarning],
    ) -> set[int]:
        """Return indices of findings the judge should review."""
        ambiguous: set[int] = set()
        for idx, finding in enumerate(findings):
            if finding.canonical not in _IDENTIFIER_CANONICALS:
                continue
            if _CONFIDENCE_SCORE.get(finding.confidence, 0.0) < self._threshold:
                ambiguous.add(idx)
                continue
            if any(w.affects(finding) for w in warnings):
                ambiguous.add(idx)
        return ambiguous

    def _judge_one(
        self,
        finding: Finding,
        all_findings: list[Finding],
        all_warnings: list[ValidationWarning],
        bundle: ClusterAnchorBundle,
    ) -> Finding | None:
        """Invoke the judge on one finding; return the adjudicated finding (or None to drop)."""
        inputs = FindingForJudge(
            finding=finding,
            sheet_excerpt=_render_sheet_excerpt(bundle.canvas, finding.value_coord),
            spec_snippet=_render_spec_snippet(finding.canonical),
            alternative_candidates=[
                other for other in all_findings
                if other is not finding and other.value_coord == finding.value_coord
            ],
            validator_warnings=[w for w in all_warnings if w.affects(finding)],
            cluster_context=(
                f"cluster_id={bundle.cluster.cluster_id} sheet={bundle.anchor_sheet_name}"
            ),
        )
        verdict = self._agent.run(ctx=bundle, inputs=inputs, provider=self._llm)
        if isinstance(verdict, AgentRunFailure):
            self.log.warning("judge_fallback_kept_finding",
                              canonical=finding.canonical, reason=verdict.reason)
            return finding
        return _apply_verdict(finding, verdict, bundle.canvas)


# ── module-level pure helpers ───────────────────────────────────────────


def _apply_verdict(
    finding: Finding,
    verdict: IdentifierVerdict,
    canvas: GridCanvas,
) -> Finding | None:
    """Return the adjudicated Finding, or None when the verdict says drop."""
    if verdict.decision == "drop":
        return None
    if verdict.decision == "keep":
        return finding
    # rewrite
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


def _render_sheet_excerpt(
    canvas: GridCanvas,
    center: tuple[str, int],
    *,
    half_rows: int = 3,
    half_cols: int = 3,
) -> str:
    """Render the cells around `center` as a fixed-width grid string for the LLM."""
    col_letter, row = center
    col = column_index_from_string(col_letter)
    r0 = max(1, row - half_rows)
    r1 = min(canvas.n_rows, row + half_rows)
    c0 = max(1, col - half_cols)
    c1 = min(canvas.n_cols, col + half_cols)

    width = 14
    lines: list[str] = []
    header_cells = [f"({get_column_letter(c)})".center(width) for c in range(c0, c1 + 1)]
    lines.append(" " * 6 + "".join(header_cells))
    for r in range(r0, r1 + 1):
        marker = "*" if r == row else " "
        row_cells = []
        for c in range(c0, c1 + 1):
            value = canvas.cell_values[r - 1][c - 1]
            text = "" if value is None else str(value)
            if len(text) > width - 2:
                text = text[: width - 5] + "..."
            row_cells.append(text.ljust(width))
        lines.append(f"{marker}{r:>4} " + "".join(row_cells))
    return "\n".join(lines)


def _render_spec_snippet(canonical: str) -> str:
    """Render the canonical's FieldSpec into a prompt-ready snippet."""
    try:
        spec = get_identifier_spec(canonical)
    except KeyError:
        return f"(no spec catalogued for {canonical})"

    lines = [f"{canonical} — {spec.description}"]
    if spec.patterns:
        lines.append("Patterns:")
        lines.extend(f"  - {p}" for p in spec.patterns)
    if spec.anti_patterns:
        lines.append("Anti-patterns:")
        lines.extend(f"  - {p}" for p in spec.anti_patterns)
    if spec.examples:
        lines.append("Examples: " + ", ".join(spec.examples))
    return "\n".join(lines)
