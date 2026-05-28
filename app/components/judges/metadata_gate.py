"""MetadataGate — routes open-vocab MetadataEntry items to MetadataFindingJudge.

Trigger: `entry.canonical is None`. Per the metadata-is-open principle
novel keys are legitimate, so the judge defaults toward `keep` and
only `rewrite`s when an obvious catalog match exists.

Verdict application:
  - keep    → entry unchanged
  - drop    → entry removed
  - rewrite → entry.canonical = alternative_canonical (verified
              against METADATA_CANONICALS by the agent's output
              validator before reaching here)

AgentRunFailure → keep the entry (fail-safe).
"""
from __future__ import annotations

from haystack import component

from app.agents._base import AgentRunFailure
from app.agents.judges.metadata import MetadataFindingJudge
from app.agents.judges.metadata.schema import (
    MetadataFindingForJudge,
    MetadataVerdict,
)
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.judges._render import render_sheet_excerpt
from app.inferencing._base import BaseProvider
from app.specs.metadata import METADATA_SPECS
from app.specs.schemas import MetadataEntry


@component
class MetadataGate(Component):
    """Adjudicate every novel-canonical MetadataEntry via MetadataFindingJudge."""

    def __init__(self, llm: BaseProvider) -> None:
        Component.__init__(self)
        self._agent = MetadataFindingJudge()
        self._llm = llm

    @component.output_types(metadata_entries=list[MetadataEntry])
    def run(
        self,
        metadata_entries: list[MetadataEntry],
        bundle: ClusterAnchorBundle,
    ) -> dict:
        if not metadata_entries:
            return {"metadata_entries": []}

        out: list[MetadataEntry] = []
        for entry in metadata_entries:
            if entry.canonical is not None:
                out.append(entry)
                continue
            adjudicated = self._judge_one(entry, bundle)
            if adjudicated is not None:
                out.append(adjudicated)
        return {"metadata_entries": out}

    def _judge_one(
        self,
        entry: MetadataEntry,
        bundle: ClusterAnchorBundle,
    ) -> MetadataEntry | None:
        """Invoke the judge; return the adjudicated entry (or None to drop)."""
        inputs = MetadataFindingForJudge(
            metadata=entry,
            metadata_catalog=_render_metadata_catalog(),
            sheet_excerpt=_render_metadata_excerpt(bundle, entry),
            cluster_context=(
                f"cluster_id={bundle.cluster.cluster_id} sheet={bundle.anchor_sheet_name}"
            ),
        )
        verdict = self._agent.run(ctx=bundle, inputs=inputs, provider=self._llm)
        if isinstance(verdict, AgentRunFailure):
            self.log.warning("judge_fallback_kept_metadata",
                              key=entry.key, reason=verdict.reason)
            return entry
        return _apply_verdict(entry, verdict)


def _apply_verdict(entry: MetadataEntry, verdict: MetadataVerdict) -> MetadataEntry | None:
    """Return the adjudicated entry, or None when the verdict says drop."""
    if verdict.decision == "drop":
        return None
    if verdict.decision == "keep":
        return entry
    return entry.model_copy(update={"canonical": verdict.alternative_canonical})


def _render_metadata_catalog() -> str:
    """Render every METADATA_SPECS entry as a prompt-ready block."""
    lines: list[str] = []
    for spec in METADATA_SPECS:
        aliases = ", ".join(spec.aliases) if spec.aliases else "(no aliases)"
        lines.append(f"- {spec.canonical} — {spec.description}")
        lines.append(f"    aliases: {aliases}")
    return "\n".join(lines)


def _render_metadata_excerpt(bundle: ClusterAnchorBundle, entry: MetadataEntry) -> str:
    """Show the cells around the entry's source cell.

    `entry.source` is a cell ref like "K4". We split it into column
    letter + row 1idx so render_sheet_excerpt can centre on it.
    """
    coord = _parse_cell_ref(entry.source)
    if coord is None:
        return "(no excerpt; source ref unparseable)"
    return render_sheet_excerpt(bundle.canvas, coord, half_rows=2, half_cols=2)


def _parse_cell_ref(ref: str) -> tuple[str, int] | None:
    """Parse 'K4' → ('K', 4). Returns None when ref doesn't match."""
    idx = 0
    while idx < len(ref) and ref[idx].isalpha():
        idx += 1
    if idx == 0 or idx == len(ref):
        return None
    try:
        return ref[:idx].upper(), int(ref[idx:])
    except ValueError:
        return None
