# Canvas Architecture — Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement each tier. This master plan is the index; per-tier plans carry the actionable steps.

**Goal:** Land the canvas architecture (per the design spec at `docs/superpowers/specs/2026-05-27-canvas-architecture-design.md`) across eight tiers totalling ~28 PRs, all merging into the `canvas-architecture` integration branch, with a final merge to `main` once the eval bar is hit.

**Architecture:** Five layers — GridCanvas (channels) → Pattern Detectors (typed records) → Semantic Resolvers (typed roles) → Per-Canonical Field Components (extraction) → LLM Judges (review). Above this: Workbook routing (clusters → roles → per-cluster dispatch).

**Tech stack:** Python 3.12, openpyxl, Haystack 2.10+ Pipeline DSL, Pydantic 2.6+, pydantic-settings, structlog, OpenTelemetry SDK 1.27+, Anthropic SDK. No new dependencies.

**Eval contract:** every PR must (a) keep all existing tests green, (b) not regress on `canvas_eval` against `dataset/extracted_2`, (c) pass CODING_STANDARD Section 10 self-review.

**Final merge bar:** canvas path beats SheetRowPlanner path on `dataset/extracted_2` by ≥5pts identifier recall AND ≥5pts identifier precision AND no stage-extraction regression.

---

## Conventions (read once, apply to every PR)

- All commits target the `canvas-architecture` branch, not `main`.
- Conventional commits (`feat:`, `chore:`, `refactor:`, `test:`, `docs:`).
- Weekly rebase from `main` into `canvas-architecture`.
- Each PR's commit body affirms CODING_STANDARD Section 10 self-review checklist.
- Python 3.12+, modern type hints (`list[X]`, `X | None`); no `Optional`/`List`/`Dict`/`Tuple`/`Union` from `typing`.
- `from __future__ import annotations` at top of every new file (codebase convention).
- Three import groups (stdlib, third-party, local), absolute imports only.
- One-line imperative docstring on every public function, class, and module.
- Function bodies ≤ 40 lines (CODING_STANDARD §2); split with named helpers if longer.
- Each tier's plan file is committed in PR 0b. Subsequent tiers' plans may be drafted as outlines and expanded just before the tier starts.
- After every commit, `make test` must pass (`pytest tests -q -m "not live"`).
- Canvas eval against `dataset/extracted_2` must not regress.

---

## Tier dependency graph

```
Tier 0  Foundations
   │
   ▼
Tier 1  Tools
   │
   ▼
Tier 2  Structure Phase   ─┐
   │                       │
   ▼                       │
Tier 3  Workbook Phase   ──┤
                            │
   ┌────────────────────────┘
   ▼
Tier 4  Field Components
   │
   ▼
Tier 5  Validators
   │
   ▼
Tier 6  Judges
   │
   ▼
Tier 7  Pipelines + Router
   │
   ▼
Tier 8  Eval + Delivery → merge to main
```

Hard dependencies are strict (Tier 1 needs Tier 0; Tier 4 needs Tier 2 + Tier 3; etc). Within a tier, PRs may land in any order if independent.

---

## Tier overview + PR map

| Tier | PRs | Focus | Per-tier plan |
|---|---|---|---|
| 0 | 4 | Foundations: ADR, design spec, plans, artifacts, specs promotion | `2026-05-27-canvas-tier-0-foundations.md` |
| 1 | 4 | Tools: build_canvas, around, query, strip detectors | `2026-05-27-canvas-tier-1-tools.md` |
| 2 | 3 | Structure phase: resolvers, axis inferrer, composer | `2026-05-27-canvas-tier-2-structure-phase.md` |
| 3 | 2 | Workbook phase: profiler, clusterer, role classifier | `2026-05-27-canvas-tier-3-workbook-phase.md` |
| 4 | 7 | Field components: per-canonical + arbiter + stages + metadata | `2026-05-27-canvas-tier-4-field-components.md` |
| 5 | 2 | Validators: cardinality + alignment + dtype + orchestrator | `2026-05-27-canvas-tier-5-validators.md` |
| 6 | 3 | Judges: spike + finding judges + phase judges + gating | `2026-05-27-canvas-tier-6-judges.md` |
| 7 | 2 | Pipelines: factories + router + reconciler | `2026-05-27-canvas-tier-7-pipelines.md` |
| 8 | 2 | Eval lift + final delivery | `2026-05-27-canvas-tier-8-eval-delivery.md` |

Per-tier plans for tiers 1–8 are drafted as outlines in PR 0b and expanded immediately before the corresponding tier starts (this keeps detail fresh and lets earlier learnings inform later detail).

---

## PR sequence by tier

### Tier 0 — Foundations [4 PRs]

```
PR 0a  docs           ADR-0008 + canvas-architecture-design.md + ARCHITECTURE.md section
PR 0b  docs           master plan + 8 tier plan files (outlines for tiers 1-8)
PR 0c  refactor       promote experiments/specs/ → app/specs/ (no behaviour change)
PR 0d  feat(artifacts) GridCanvas, StructureBag, LayoutHint, Finding, Verdict, LayoutAxes
```

Eval expectation: no change (artifacts and specs only).

### Tier 1 — Tools [4 PRs]

```
PR 1a  feat(tools/canvas)  build + around + query (port from experiments)
PR 1b  feat(tools/canvas)  strip detectors — date, numeric, text strips
PR 1c  feat(tools/canvas)  strip detectors — visual (color, bold, border), merge, kv, repeating
PR 1d  feat(tools/canvas)  plan_marker_cluster + dtype profiles (per row + per col)
```

Eval expectation: no change (tools only, not yet consumed).

### Tier 2 — Structure Phase [3 PRs]

```
PR 2a  feat(structure)  pattern→semantic resolvers (header_band, data_row_range,
                        stage_arena, stage_band, subfield_cluster, section_boundary)
PR 2b  feat(structure)  axis_inferrer + layout_composer
PR 2c  feat(structure)  phase orchestrator + anchor_picker + inheritance_verifier
```

Eval expectation: LayoutHints visualisable for every file in extracted_2; no extraction yet.

### Tier 3 — Workbook Phase [2 PRs]

```
PR 3a  feat(workbook)  profiler + clusterer + role_classifier
PR 3b  feat(workbook)  phase orchestrator + aggregator + composite-key dedup
```

Eval expectation: multi-sheet workbooks (Eastman, 63261, MAIN FALL) correctly clustered; no extraction yet but cluster routing visible in logs.

### Tier 4 — Field Components [7 PRs]

```
PR 4a  feat(components)              BaseCanonicalComponent contract
PR 4b  feat(components/identifiers)  io_number + quantity (anchor pair)
PR 4c  feat(components/identifiers)  code trio + name trio + sibling resolution
PR 4d  feat(components/identifiers)  date trio + stage-wins integration
PR 4e  feat(components/identifiers)  IdentifierArbiter (cross-canonical)
PR 4f  feat(components/stages)       Arena → Band → ColumnTyping → PerPli
PR 4g  feat(components/metadata)     Collector + Classifier + PerPliBinder
```

Eval expectation by end of Tier 4: identifier recall ≥68%, precision ≥65% (parity with current experiments baseline).

### Tier 5 — Validators [2 PRs]

```
PR 5a  feat(validators)  cardinality + row_alignment + date_trio
PR 5b  feat(validators)  stage_wins + merge_alignment + quantity_dtype + orchestrator
```

Eval expectation: validator warnings visible per finding; no recall/precision change but ambiguous findings flagged for the next tier.

### Tier 6 — Judges [3 PRs]

```
PR 6a  feat(agents/judges)  judge spike — identifier finding judge end-to-end +
                            ADR-0009 (judge architecture lessons)
PR 6b  feat(agents/judges)  full finding + phase judges (identifier, stage, metadata)
PR 6c  feat(pipelines)      judge gating (confidence + validator triggers)
```

Eval expectation: +5pts identifier recall from judge arbitration on ambiguous canonicals (`shipment_date`, `color_name`, etc).

### Tier 7 — Pipelines [2 PRs]

```
PR 7a  feat(pipelines/canvas)  make_*_pipeline factories + router (canvas vs legacy)
PR 7b  feat(pipelines)         reconciler + canvas-as-default switch
```

Eval expectation: end-to-end PLI JSON output via canvas path; tunable per-sheet routing.

### Tier 8 — Eval + Delivery [2 PRs]

```
PR 8a  feat(eval) + test(integration)  canvas_eval lifted to app/, smoke tests against
                                        extracted_2, docs update
PR 8b  chore                            retire experiments/p3_visual, journey entry,
                                        final merge to main
```

Eval expectation: canvas beats legacy by ≥5pts on both metrics; merge unlocked.

---

## Subagent-driven execution

Per tier (per `superpowers:subagent-driven-development`):

```
1. Extract tier plan + all tasks into TodoWrite
2. For each task:
   a. Dispatch implementer subagent with the task text + context
   b. Subagent: implements, tests, self-reviews against CODING_STANDARD §10, commits
   c. Dispatch spec-reviewer subagent
   d. If spec-reviewer flags gaps: implementer subagent fixes; re-review
   e. Dispatch code-quality-reviewer subagent (gets git SHAs)
   f. If reviewer flags issues: implementer subagent fixes; re-review
   g. Mark task complete
3. After all tasks in tier: dispatch final code-reviewer for the whole tier
4. Run eval against extracted_2; verify no regression
5. Land tier as one or more PRs into canvas-architecture
6. Update master-plan checklist below with tier completion
```

### Tier progress checklist (update as tiers land)

- [ ] **Tier 0** Foundations
  - [ ] PR 0a — docs (ADR-0008 + design spec + ARCHITECTURE section)
  - [ ] PR 0b — plans (master + Tier 0)
  - [ ] PR 0c — promote specs to app/
  - [ ] PR 0d — artifacts module
- [ ] **Tier 1** Tools
  - [ ] PR 1a — build + around + query
  - [ ] PR 1b — date/numeric/text strip detectors
  - [ ] PR 1c — visual/merge/kv/repeating detectors
  - [ ] PR 1d — plan_marker + dtype profiles
- [ ] **Tier 2** Structure phase
  - [ ] PR 2a — resolvers
  - [ ] PR 2b — axis_inferrer + composer
  - [ ] PR 2c — phase orchestrator + anchor_picker
- [ ] **Tier 3** Workbook phase
  - [ ] PR 3a — profiler + clusterer + role_classifier
  - [ ] PR 3b — orchestrator + aggregator
- [ ] **Tier 4** Field components
  - [ ] PR 4a — BaseCanonicalComponent
  - [ ] PR 4b — io_number + quantity
  - [ ] PR 4c — code/name trios + siblings
  - [ ] PR 4d — date trio + stage-wins
  - [ ] PR 4e — IdentifierArbiter
  - [ ] PR 4f — stage components
  - [ ] PR 4g — metadata components
- [ ] **Tier 5** Validators
  - [ ] PR 5a — cardinality + row_alignment + date_trio
  - [ ] PR 5b — stage_wins + merge_alignment + dtype + orchestrator
- [ ] **Tier 6** Judges
  - [ ] PR 6a — judge spike + ADR-0009
  - [ ] PR 6b — finding + phase judges
  - [ ] PR 6c — judge gating
- [ ] **Tier 7** Pipelines
  - [ ] PR 7a — factories + router
  - [ ] PR 7b — reconciler + canvas-default
- [ ] **Tier 8** Eval + delivery
  - [ ] PR 8a — eval lift + smoke tests
  - [ ] PR 8b — retire experiments, journey, final merge

---

## Coexistence with legacy

For the duration of the canvas-architecture branch:

- `app/pipelines/extract.py` (legacy SheetRowPlanner path) stays untouched
- `experiments/p3_visual/canvas_probe/` stays as reference until Tier 8
- Tier 7's router decides per sheet whether to use canvas or legacy path
- Tier 7 keeps legacy as fallback; Tier 8b retires it

This means **no regression risk to main during canvas development**. If canvas hits unexpected issues on specific files, the legacy path still serves them.

---

## References

- **Design spec:** `docs/superpowers/specs/2026-05-27-canvas-architecture-design.md`
- **ADR-0008:** `docs/adrs/0008-canvas-architecture.md`
- **ADR-0007** (foundation): `docs/adrs/0007-pipeline-architecture-redesign.md`
- **CODING_STANDARD.md** — Section 10 self-review checklist; Section 11 framework primitives
- **CLAUDE.md** — LLM-as-reviewer principle
- **Ground truth:** `dataset/extracted_2/dataset_plis_bulk.json`
- **Reference impl:** `experiments/p3_visual/canvas_probe/` (retired in Tier 8)
