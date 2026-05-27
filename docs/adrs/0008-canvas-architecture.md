# ADR-0008 — Canvas Architecture (measurement substrate + per-canonical components + two-tier judges)

**Status:** Draft (in implementation across canvas-architecture branch, 2026-05-27)
**Builds on:** ADR-0007 (seven framework primitives + Haystack DSL)
**Supersedes:** none yet — coexists with SheetRowPlanner path until Tier 7

## Context

ADR-0007 established seven framework primitives and a Haystack Pipeline DSL. The
extraction logic itself, however, still lives in one large `find_tabular_identifiers`
function and a SheetRowPlanner agent. Three problems surfaced during P3
experimentation and the canvas eval iteration sessions:

1. **The mega-function does too much.** `find_tabular_identifiers` mixes alias matching,
   word-boundary rules, anti-pattern rejection, sibling resolution, bare-CODE positional
   logic, single-column arbitration, and dtype gating across all 11 identifier
   canonicals. A single fix requires reasoning about all 11 together. Five iterative
   patches in one session lifted recall 44% → 68% and precision 30% → 65%, but each
   patch grew the function and tightened its cross-canonical coupling.

2. **Channels are too raw.** Today's extractors reach directly into
   `canvas.channels["fill_color"][r][c]` for spatial decisions. There is no semantic
   layer between "what colour is this cell" and "this column is part of a stage band."
   Every extractor redoes the same pattern detection work.

3. **Workbook structure is invisible.** The pipeline runs on `wb.active` and treats
   each sheet as a standalone problem. Multi-sheet workbooks (Eastman 17 PLIs across
   17 sheets, 63261-TNA mixed-layout sheets, MAIN FALL multi-template workbooks)
   are systematically mis-handled because workbook-level routing doesn't exist.

The P3 canvas probe in `experiments/p3_visual/canvas_probe/` proved the substrate
shape works — measurement channels, strip detection, k:v and tabular extraction
paths. The next step is lifting it into `app/` with the right component decomposition
and adding the missing layers (workbook routing, semantic resolvers, per-canonical
components, two-tier judges).

## Decision

Adopt a **canvas-as-substrate architecture** with five distinct layers:

### Layer 1 — GridCanvas (measurement)

Channels remain raw per-cell measurements: dtype, density, fill_color, border, merge,
bold, date_like, dtype_run_row, dtype_run_col, date_cluster, density_cluster,
repeating_row_id, repeating_col_id, plan_marker, empty_row, empty_col, merge_shape,
fill_color_cluster, column_dtype_dominant, row_dtype_profile, col_dtype_profile.

The canvas is the **shared spatial substrate**. Every layer above writes additional
channels back onto it (e.g., `finding_io_number` channel marks claimed cells) while
also emitting typed records for iteration.

### Layer 2 — Pattern detectors (typed structural records)

Each detector reads channels and emits typed records into a `StructureBag`. Parallel,
independent, no dependencies between detectors:

- DateStrip, IntStrip (magnitude-tagged), FloatStrip, SameLengthStrip, LongTextStrip
- ColorStrip (vertical, horizontal), BoldStrip, BorderedBox
- MergeSpan (vertical, horizontal), NonMergedStrip, MergedColumnStrip
- KvBlock, RepeatingRowGroup, PlanMarkerCluster

### Layer 3 — Semantic resolvers (typed roles)

A DAG ordered by dependencies. Each resolver runs once and interprets patterns into
semantic roles:

```
HeaderBandResolver           ← BoldStrip, ColorStrip-Horiz, spec matches
  ├─ DataRowRangeResolver
  └─ SectionBoundaryResolver
        └─ StageArenaResolver         ← DateStrip + PlanMarkerCluster + BorderedBox
              └─ StageBandResolver
                    └─ SubfieldClusterResolver
AxisInferrer                 ← combines everything → LayoutAxes
LayoutComposer               ← emits the final LayoutHint
```

### Layer 4 — Per-canonical field components

One component per identifier canonical (11 total) plus per-stage detection components.
Each follows a five-step internal pipeline:

```
locate → filter → claim → arbitrate → emit
```

The component encapsulates that canonical's policy: spec aliases, anti-patterns,
dtype gates, sibling resolution membership, structural-extraction dependencies.
Cross-cutting concerns (sibling resolution across families, single-canonical-per-PLI,
stage-wins, cardinality, merge-alignment) live in an `IdentifierArbiter` that runs
after all per-canonical components.

### Layer 5 — Two-tier LLM judges

Per CLAUDE.md principle "LLM as reviewer, not producer":

- **PerFindingJudge** fires per ambiguous finding (low confidence OR validator
  warning OR multiple candidate columns).
- **PhaseJudge** fires per phase only when PerFinding can't resolve cross-canonical
  conflicts.
- Both are wrapped by `JudgeGateComponent` instances; pipelines never invoke agents
  directly. Det wins on disagreement.

### Workbook layer (above per-sheet pipeline)

`WorkbookPipeline` clusters sheets by structural signature similarity (NonBlankMask
+ DtypeFingerprint + LabelTextPositions), classifies each cluster as `pli_cluster`
or `other_sheets`, and dispatches the SheetPipeline once per sheet in each
`pli_cluster`. Aggregator unions findings across clusters with `(io_number, style_code)`
composite-key dedup.

### Pipeline composition — Style B

Primary entry point is one mega-factory `make_canvas_pipeline()` composing the whole
graph. Sub-factories (`make_structure_pipeline`, `make_identifier_phase_pipeline`,
`make_workbook_pipeline`) exist for testability — each returns a standalone Pipeline
runnable in isolation.

### Hierarchy enforcement

The seven primitives from ADR-0007 stay in their homes:
- `app/tools/canvas/` — pattern detectors, semantic primitives (stateless, `@tool`)
- `app/components/structure/` — pattern detector components, semantic resolvers,
  axis inferrer, layout composer
- `app/components/workbook/` — profiler, clusterer, role classifier, aggregator
- `app/components/identifiers/<canonical>.py` — per-canonical extractors
- `app/components/stages/` — arena, band, column-typing, per-pli
- `app/components/metadata/` — collector, classifier, per-pli binder
- `app/components/validators/` — structural-query validators
- `app/components/judges/` — judge gate components (wrappers)
- `app/agents/judges/<judge>/` — the actual LLM judge agents
- `app/pipelines/canvas/` — factories: workbook, structure, identifiers, stages,
  metadata, main

An import-graph CI test enforces no upward violations
(`tests/architecture/test_import_hierarchy.py`).

## Why not alternatives

**Why not extend SheetRowPlanner with more rules?** The mega-function approach
hit a complexity ceiling. Each new canonical or quirk increased cross-canonical
coupling. Per-canonical components let each field's policy live alone.

**Why not pure LLM extraction?** Cost, latency, and reproducibility. Det extraction
runs in milliseconds per sheet at zero per-call cost; LLM judges fire only on
genuinely ambiguous findings (~15% of findings on typical sheets). This preserves
the O(sheets) LLM budget principle from ADR-0003.

**Why not skip the structure layer and route extractors directly off channels?**
Tried in experiments; failed. Every extractor needs the same pattern detection
(header band, date strips, arenas). Centralising as a phase removes ~70% of
duplicated logic and makes constraints (stage-wins, cardinality) expressible
as structural queries.

**Why not a single `LayoutDetector` agent that decides everything in one call?**
That's what `LayoutHinter` is today. It conflates layout shape with field
location, and its output isn't easy to validate or compose. Splitting into
deterministic structure phase + per-canonical components keeps LLM calls narrow
and reviewable.

## Consequences

**Positive:**
- Each canonical's policy is one small file with focused tests.
- Workbook-level routing handles multi-sheet xlsx files correctly.
- Adding a new canonical = adding a new component, no central mega-function edit.
- Stage extraction extends to FA26-style files (no plan-marker text) via
  BorderedBox + ColorStrip fallbacks.
- LLM cost is predictable: zero on clean sheets, bounded on ambiguous ones.

**Negative:**
- ~25 new component files vs the current handful. Mitigated by `BaseCanonicalComponent`
  carrying boilerplate.
- StructurePhase has a two-pass dependency between AxisInferrer and
  StageArenaResolver. Two passes per sheet; cheap but non-trivial.
- Long-lived integration branch (`canvas-architecture`) needs weekly rebase
  against `main`.
- Per-cluster LayoutHint inheritance assumes cluster similarity ≥ 0.95; below
  that, full StructurePhase falls back per sheet.

**Migration path:**
- Legacy SheetRowPlanner path stays running in parallel until Tier 7 router lands.
- `experiments/p3_visual/canvas_probe/` stays as reference until Tier 8 retirement.
- Canvas path is gated behind a tuning flag until parity is reached on
  `dataset/extracted_2`.

## Status notes

Tracked across 28 PRs in 8 tiers on the `canvas-architecture` branch:

- Tier 0 — foundations (this ADR + design spec + plans + artifacts)
- Tier 1 — tools (build_canvas, around, query, strip detectors)
- Tier 2 — structure phase (resolvers + axis inferrer + composer)
- Tier 3 — workbook phase (profiler + clusterer + roles + aggregator)
- Tier 4 — field components (per-canonical + arbiter + stages + metadata)
- Tier 5 — validators (structural-query validators)
- Tier 6 — judges (per-finding + per-phase, gated on confidence)
- Tier 7 — pipelines (factories + router)
- Tier 8 — eval + delivery (canvas_eval lift + merge to main)

The eval bar for merging `canvas-architecture` → `main`: canvas path beats
SheetRowPlanner on `dataset/extracted_2` by ≥5pts identifier recall AND
≥5pts identifier precision AND no stage regression.

## References

- **ADR-0007** — seven framework primitives this builds on
- **docs/superpowers/specs/2026-05-27-canvas-architecture-design.md** — full design
- **docs/superpowers/plans/2026-05-27-canvas-architecture-master-plan.md** — PR sequence
- **CLAUDE.md** — LLM-as-reviewer principle, extensibility axes
- **CODING_STANDARD.md** — Section 11 framework primitives, Section 10 self-review
- **experiments/p3_visual/canvas_probe/** — current canvas probe (reference until retired)
