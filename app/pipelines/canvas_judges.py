"""Canvas-architecture judges pipeline factory.

Wires every canvas-arch judge gate into a single Haystack `Pipeline`.
Five components, two internal edges, three branches:

  identifier_finding ── audits ──► identifier_phase ── findings ──►
  stage_finding      ── audits ──► stage_phase      ── stages_per_row ──►
  metadata                                          ── metadata_entries ──►

Pipeline edges (internal):
  identifier_finding.audits → identifier_phase.audits
  stage_finding.audits      → stage_phase.audits

Pipeline inputs (caller-supplied via `pipeline.run({...})`):
  identifier_finding: findings, warnings, bundle
  identifier_phase:   raw_findings, warnings, bundle
                       (raw_findings = the same findings passed to
                       identifier_finding; the phase gate needs them
                       directly so it can override per-finding outcomes)
  stage_finding:      stages_per_row, bundle
  stage_phase:        raw_stages_per_row, warnings, bundle
  metadata:           metadata_entries, bundle

Pipeline outputs (after `pipeline.run(...)`):
  identifier_phase.findings        — final identifier bag
  stage_phase.stages_per_row       — final per-PLI stage map
  metadata.metadata_entries        — final metadata list

The factory is composed at the service layer (option B from the
Tier 6 design discussion): the validators pipeline runs first, the
judges pipeline runs second, and the reconciler runs third. The
service layer chains them; this factory only owns the judges DAG.
"""
from __future__ import annotations

from haystack import Pipeline

from app.components.judges.identifier_finding_gate import IdentifierFindingGate
from app.components.judges.identifier_phase_gate import IdentifierPhaseGate
from app.components.judges.metadata_gate import MetadataGate
from app.components.judges.stage_finding_gate import StageFindingGate
from app.components.judges.stage_phase_gate import StagePhaseGate
from app.inferencing._base import BaseProvider


def make_canvas_judges_pipeline(llm: BaseProvider) -> Pipeline:
    """Return a Haystack Pipeline wiring every canvas judge gate.

    Same `llm` provider is shared across all five gates. The factory
    is intentionally simple — only structural edges live here; the
    triggers (when to invoke each judge) live inside the gates.
    """
    pipeline = Pipeline()

    pipeline.add_component("identifier_finding", IdentifierFindingGate(llm=llm))
    pipeline.add_component("stage_finding",      StageFindingGate(llm=llm))
    pipeline.add_component("metadata",           MetadataGate(llm=llm))
    pipeline.add_component("identifier_phase",   IdentifierPhaseGate(llm=llm))
    pipeline.add_component("stage_phase",        StagePhaseGate(llm=llm))

    pipeline.connect("identifier_finding.audits", "identifier_phase.audits")
    pipeline.connect("stage_finding.audits",      "stage_phase.audits")

    return pipeline
