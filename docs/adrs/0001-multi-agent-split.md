# 0001 — Multi-agent split

**Date:** 2026-05-12 (microservice scaffold); architecture brainstormed 2026-05-07
**Status:** Accepted

## Context

The predecessor `tna_parser` package used a single-prompt baseline: one LLM call received a full sheet grid and returned a complete `ExtractionResult`. This was validated against the DKN benchmark file (single-sheet, columnar, 3 PLIs). Results were:

- PLI recall: 100%
- Field precision/recall: 71% (v1) → 100% after faithful-extraction prompt fix (v2)
- Stage recall: 83% (persisted despite explicit prompt instructions)

The stage recall failure exposed the core problem: a generalist prompt with many rules cannot reliably handle multiple simultaneous concerns (field extraction, stage canonicalization, boundary detection, layout variance). When the dataset was inspected more broadly, six distinct layout families surfaced — scattered KV, multi-row columnar, vertical-merge, stacked stage bands, total-row footers, multi-sheet with noise. Each family exercised different failure modes for the single-prompt approach.

Additionally, the single-prompt approach scales poorly: larger files (1000+ row GUESS master files) would exhaust context.

## Decision

Split the pipeline into specialist agents, each with narrow input, narrow output schema, and narrow tool access:

1. **SheetClassifier** — selects relevant sheets from a workbook summary.
2. **LayoutFingerprinter** (later superseded by SheetSurveyor) — detects structural signals.
3. **BoundaryFinder** (later superseded by SheetRowPlanner) — finds PLI row boundaries.
4. **IdentityLocator** — finds canonical identity fields.
5. **QuantityDateLocator** — finds quantity + date fields.
6. **StageLocator** — finds and canonicalises stage columns.

Each agent uses a shared `@tool`-decorated tool registry. Agents emit typed Pydantic bridge artifacts (`PLIBoundaries`, `FieldMap`, `StageBandSet`). Deterministic appliers (`apply_field_map`, `apply_stage_band_set`) consume these artifacts.

Routing between agents is driven by structural signals detected by the Inspector/LayoutFingerprinter — never by supplier or format names.

This architecture was implemented in the `tna-service` Spec1 microservice (commits 2026-05-12 to 2026-05-13, ~40 tasks).

## Consequences

**Easier:**
- Stage recall improves: the dedicated StageLocator prompt focuses only on canonicalisation.
- Each agent is independently testable with a FakeLLM stub.
- Novel layouts degrade to a generic-explorer fallback rather than crashing.
- LLM cost scales with sheet count + sample size, not full-grid token count.

**Harder / constrained:**
- More moving parts: ~6 agents vs 1 prompt.
- Agent coordination state must be threaded through an orchestrator.
- Debugging a pipeline failure requires identifying which agent produced a bad artifact.

**What we gave up:**
- Single-prompt simplicity. The `tna_parser` baseline is retained in `evals/` as a regression reference but is not the production path.

## Alternatives considered

- **Chain-of-thought in a single prompt.** Rejected: large grids hit context limits; CoT cannot reliably handle concurrent layout-detection + stage-canonicalization + boundary-arithmetic in one pass.
- **LangGraph orchestrator.** Evaluated but deferred: the tool-using `AgentRunner` + manual orchestrator gave full control over retry policy and error propagation without the LangGraph dependency and its opaque state machine. The decision was "own the graph, not adopt a framework."
- **Format-name routing (`if layout == "DKN":`).** Explicitly rejected: every new supplier requires a new branch; unknown suppliers hard-fail. Signal-based routing is more robust. See `docs/PRINCIPLES.md`.
