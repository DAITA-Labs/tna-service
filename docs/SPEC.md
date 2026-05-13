# TNA Service — Core Agentic Architecture + Eval Framework

> **Spec 1 of 2.** Covers the brain of a new microservice (`tna-service/`) that extracts structured PLI/Stage JSON from any TNA xlsx, plus the eval framework that gates every change to it. **Spec 2** (deferred) covers the service surface (FastAPI shape, the xlsx-upload UI with top/bottom JSON view, expanded ops tooling).

**Date:** 2026-05-13
**Status:** Updated — SheetRowPlanner pipeline (supersedes 2026-05-12 draft)
**Supersedes:** Tactical iteration on `tna_parser/` (kept alive as fallback during V1 rollout)

---

## 1. Goal

Extract every PLI and its stages from any TNA xlsx — regardless of supplier format — and return structured JSON that round-trips with the user's label schema. Be **robust to merchant data quirks** (corrupted headers, stacked sub-tables, totals rows, vertical-merge sub-rows, multi-band stage sections), **observable** (every extraction's behavior is measurable), and **incrementally adaptable** (a new TNA family is a small change, never a rewrite).

**Non-goals for Spec 1:** UI, auth, DB persistence, request streaming, multi-tenancy. These are Spec 2 or later.

## 2. Architecture overview

### 2.1 High-level shape

```
                              ┌──────────────────┐
                              │   Orchestrator   │
                              └────────┬─────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                   ▼
           ┌──────────────┐   ┌───────────────┐   ┌───────────────┐
           │  Per-sheet   │   │  Per-sheet    │   │  Workbook-    │
           │  Planning    │   │  Extraction   │   │  level valid. │
           ├──────────────┤   ├───────────────┤   ├───────────────┤
           │ SheetSurveyor│   │ FieldNamer    │   │ SourceCellVer │
           │ SheetRowPlanr│   │ apply_plan    │   │ HeaderMatchVer│
           │ validate_plan│   │ (100% det,    │   │ CoverageVer   │
           │ LayoutHinter │   │  LLM-free)    │   │ DropoutVer    │
           │ (cond.)      │   │               │   │               │
           │ PlanReviewer │   │               │   │ (deterministic)│
           │ (cond.)      │   │               │   │               │
           └──────┬───────┘   └───────┬───────┘   └───────┬───────┘
                  │                   │                    │
                  └───────────────────┼────────────────────┘
                                      ▼
                               ┌──────────────┐
                               │  Reconciler  │
                               │ (lenient v1) │
                               └──────┬───────┘
                                      ▼
                              ExtractionResult
                             + Warnings
                             + per-PLI source_cells
```

The pipeline separates planning from extraction. **SheetRowPlanner** (deterministic) emits a `SheetPlan` artifact describing the full row/column structure; optional LLM agents (`LayoutHinter`, `PlanReviewer`) review and correct the plan when signals are ambiguous. **FieldNamer** (LLM) maps header labels to canonical field names. **apply_plan** (100% deterministic, zero LLM calls) resolves PLIs from the plan. **4 extraction validators** run workbook-level after all sheets are aggregated. The **Reconciler** merges everything. Nothing is auto-dropped in V1 — strict mode lives behind a future config flag.

### 2.2 Orchestration phases (detailed)

The orchestrator drives eight phases (0–7). Each phase has a domain-anchored purpose; the per-sheet planning loop (phases 2–5) runs per relevant sheet.

**Phase 0 — Workbook summary** *(deterministic tool)*. Open xlsx via openpyxl into a cached `WorkbookCtx`. `workbook_summary()` computes sheet names, dims, and file size.

**Phase 1 — Sheet Classification** *(LLM)*. `SheetClassifier` decides "TNA-relevant or noise?" for each sheet. Catches GUESS-style summary/lab/log sheets. Output: `relevant_sheets: list[str]`.

**Per-sheet loop (Phases 2–5):**

**Phase 2 — Survey** *(deterministic)*. `SheetSurveyor` reads merged regions, sample rows, and structure signals, emitting `SheetSignals` — a compact structured summary of the sheet's observable features (merge map, header candidates, non-empty row density, vocabulary overlap counts). No LLM call.

**Phase 3 — Plan** *(deterministic core + conditional LLM review)*. Three sub-phases:

- **3 — `SheetRowPlanner`** *(deterministic)*: consumes `SheetSignals` and emits a draft `SheetPlan` — the unified artifact describing every row's role, PLI organization mode, stage band geometry, and KV anchors. The planner dispatches across three orthogonal axes: `pli_mode` ∈ {`ROW_PER_PLI`, `SECTION_PER_PLI`, `SHEET_IS_PLI`}, `stage_scope` ∈ {`SHEET_LEVEL`, `SECTION_LOCAL`, `PLI_LOCAL`}, and per-row `sub_row_role` ∈ {`PLAN`, `ACTION`, `ACTUAL`, `DEVIATION`}.

- **3a — `validate_plan` (Tier 1 + Tier 2)** *(deterministic, mandatory)*: Tier 1 checks structural invariants (reference integrity, row uniqueness, header contiguity, block non-overlap, coverage partition, sub-row consistency). Tier 2 checks statistical sanity (sequence match, total arithmetic, date band density, KV anchor adjacency, PLI count sanity, identity column coverage, vocabulary overlap). Errors trigger re-plan with hints; warnings surface to Tier 3.

- **3b — `LayoutHinter`** *(LLM, conditional)*: fires only when the planner signals ambiguous layout regions. Consumes `SheetSignals` + ambiguity markers; emits `LayoutHints` (mode suggestion + rationale). Input to a re-plan pass if needed.

- **3c — `PlanReviewer`** *(LLM judge, conditional)*: fires when Tier 1/2 produced warnings, `plan.confidence` < 0.85, or `pli_mode ∈ {SECTION_PER_PLI, SHEET_IS_PLI}`. Receives the plan summary + 3-5 sample rows + Tier 2 warnings; emits `PlanVerdict` (`looks_correct` | `needs_fix`). If `needs_fix`, row corrections are applied and the plan re-validates. Det signal wins on disagreement — reviewer is advisory.

**Phase 4 — Field naming** *(LLM)*. `FieldNamer` receives the `SheetPlan`'s header labels and stage column names; emits `CanonicalNameMap` mapping raw labels to canonical field names (io_number, style_code, etc.). One LLM call per sheet; no row iteration.

**Phase 5 — Apply** *(deterministic, 100% LLM-free)*. `apply_plan(ctx, plan, name_map)` resolves every PLI from `SheetPlan + CanonicalNameMap`. Dispatches on `pli_mode`, `stage_scope`, and `RowSpec.role`/`sub_row_role` — no string-keyed heuristics, no supplier-name logic. If a plan reference is missing in the workbook, raises a typed error (orchestrator logs + emits Warning). Emits `source_cells: {field → A1 address}` on every PLI. A static analysis check enforces that `apply_plan` and its callees do not import `agents` or `llm_provider`.

**Phase 6 — Extraction Validation** *(deterministic, 4 checks in parallel)*. After all sheets are aggregated:
- `SourceCellVerifier` — for each PLI, does the cell at `source_cells[field]` still contain the extracted value?
- `HeaderMatchVerifier` — for each canonical field's source column, does the header text contain canonical-field vocabulary?
- `CoverageVerifier` — extracted PLI count vs candidate-row count; flags below 80%.
- `FieldDropoutVerifier` — canonical fields populated in <50% of PLIs.

Output: `list[ValidationFinding]` with severity `info | warn`.

**Phase 7 — Reconcile** *(deterministic)*. Workflow output passes through unchanged. Validation findings become Warnings attached to the result. `extraction_confidence = 0.7 · mean(workflow_per_field_confidence) + 0.3 · (1 − validator_warn_rate)`. `source_cells` preserved on every PLI.

### 2.3 Locked orchestration decisions

| # | Decision | Locked choice | Rationale |
|---|---|---|---|
| D1 | Per-sheet parallelism in Phases 2–5 | **Sequential V1**, max-concurrency knob deferred | Most labeled files are 1–3 sheets; Anthropic rate-limit risk; simpler error handling |
| D2 | LLM responsibility split | **LLM does vocabulary (FieldNamer) and judgment (PlanReviewer); det does row arithmetic (SheetRowPlanner)** | Row arithmetic is where LLMs fail; vocabulary mapping is where they excel |
| D3 | `apply_plan` determinism | **Zero LLM calls in apply_plan, enforced by static analysis test** | Guarantees identical output on every run for same SheetPlan; debugging isolated to planning phase |
| D4 | Validation timing for extraction validators | **After all sheets aggregated** (Phase 6) | Cross-sheet context available to verifiers; simpler than per-sheet validation merge |
| D5 | Retry policy | **1 retry with error context**, uniform across LLM agents | Retry-with-context fixes JSON-as-string artifacts reliably |
| D6 | Plan validation tiers | **Tier 1 (structural) + Tier 2 (statistical) mandatory det; Tier 3 (PlanReviewer) conditional LLM** | Det catches the most common planning errors fast; LLM reviewer fires only when there's real ambiguity |
| D7 | `PlanReviewer` firing condition | **Confidence < 0.85 OR Tier 1/2 warnings OR rare pli_mode** | Keeps median case at 1 LLM call per sheet (FieldNamer only); reviewer adds a second call only when warranted |
| D8 | Cross-sheet PLI aggregation | **Concatenate**, preserve `source_sheet` on every PLI, no dedup | Different sheets genuinely hold different PLIs (GUESS master files); dedup would mask data |
| D9 | SheetPlan 3-axis design | **pli_mode × stage_scope × sub_row_role are orthogonal** | Every observed layout family is a point in this space; new families add rules, not new enum cases |
| D10 | Telemetry granularity | **Per-phase + per-agent histograms; per-validator counters; per-file gauges** (PLI count, retry count, cost) | Lets us correlate prompt changes to specific agent/phase behavior in Grafana |

These ten are locked by review; revisiting any of them requires an ADR.

## 3. Incremental Adaptability Contract

This is the headline NFR. Every axis a new TNA family can differ along has a dedicated additive extension point.

| New thing arrives | What you change | What you do NOT touch |
|---|---|---|
| New layout shape (e.g. diagonal KV, nested multi-section) | Add rules in `planner/row_classifier.py` or `planner/block_segmenter.py`; add `RowSpec.role` enum value if needed | LLM agents, validators, eval, orchestrator, `apply_plan` dispatch (add one branch) |
| New canonical field on `PLI` | Add Pydantic field; add vocabulary to `FieldNamer` prompt | All existing extraction; eval auto-picks the field up if labels include it |
| New non-PLI row pattern | Add a `RowSpec.role` value + detection rule in `row_classifier`; add branch in `apply_plan` | All other roles |
| New supplier header vocabulary | Add term to FieldNamer prompt's vocab section (data-only) | Planner, applier, all other agents |
| New tool | One `@tool`-decorated function in `workbook_tools/` | All existing components |
| New extraction validator | One file in `validation/` | Workflow pipeline; other validators |
| New labeled file with no rules changed | Drop JSON in `dataset/extracted/` | Anything else |

A PR that touches more than two columns above gets a yellow flag in code review.

**Enforcement primitives:**
- `apply_plan` dispatches on `pli_mode`, `stage_scope`, `RowSpec.role`, `sub_row_role` enums — no string-keyed logic
- `tools/` are pure functions, `@tool`-registered into a process-wide `TOOL_REGISTRY`; det components and LLM agents share the same registry
- Pydantic models use `extra="ignore"` so additive schema changes don't break old labels
- Eval runner discovers labeled files at runtime
- Static analysis test enforces the LLM-free boundary around `apply_plan`

## 4. Directory layout

New microservice at `F:\DAITA\ARENA\TNA\tna-service\` (greenfield — `tna_parser/` stays as fallback during rollout).

```
tna-service/
├── pyproject.toml              uv-managed; fastapi, pydantic, anthropic, openpyxl,
│                               pydantic-settings, structlog, prometheus-client, starlette-prometheus
├── Makefile                    make eval / test / serve / build / lint / fmt
├── Dockerfile
├── docker-compose.yml          api + prometheus + grafana (telemetry from day 1)
├── .env.example                ANTHROPIC_API_KEY, ANTHROPIC_MODEL, APP_ENV, LOG_LEVEL, ...
├── .python-version
│
├── app/
│   ├── core/                   cross-cutting: logging, telemetry, prompt loader
│   │
│   ├── enums/                  PliMode, RowRole, SubRowRole, StageScope, StageLayoutMode
│   │
│   ├── models/
│   │   ├── extraction.py       PLI, Stage, ExtractionResult, Source (unchanged output schema)
│   │   ├── workbook.py         WorkbookCtx, Cell, MergedRegion
│   │   └── artifacts.py        SheetSignals, RowSpec, KVAnchor, StageBandSpec, PliBlock,
│   │                           SheetPlan, CanonicalNameMap, LayoutHints, PlanVerdict,
│   │                           ValidationFindings
│   │
│   ├── repositories/
│   │   ├── workbook_repo.py    WorkbookCtx lifecycle
│   │   └── workbook_tools/     10 @tool functions + TOOL_REGISTRY
│   │       ├── _registry.py    @tool decorator + process-wide registry
│   │       ├── survey.py       list_sheets, workbook_summary
│   │       ├── bulk_read.py    peek_sheet, sample_rows, read_range
│   │       ├── targeted.py     read_row, read_relative, get_cell_at
│   │       ├── structure.py    get_merged_regions, count_non_empty_rows_in_column
│   │       └── search.py       find_value
│   │
│   ├── services/
│   │   ├── llm_provider.py     LLMProvider Protocol + AnthropicProvider
│   │   ├── agents/
│   │   │   ├── _base.py        AgentSpec, AgentRunner, RetryPolicy
│   │   │   ├── sheet_classifier.py   TNA-relevant vs noise → relevant_sheets[]
│   │   │   ├── layout_hinter.py      (NEW) conditional layout hint agent → LayoutHints
│   │   │   ├── plan_reviewer.py      (NEW) LLM-as-judge → PlanVerdict
│   │   │   └── field_namer.py        (NEW) header labels → CanonicalNameMap
│   │   ├── planner/            (NEW subsystem — all deterministic)
│   │   │   ├── surveyor.py          SheetSurveyor → SheetSignals
│   │   │   ├── row_classifier.py    classify each row → RowSpec.role
│   │   │   ├── block_segmenter.py   detect PliBlock sections
│   │   │   ├── kv_anchor_detector.py find KVAnchor pairs
│   │   │   ├── stage_band_detector.py detect StageBandSpec geometry
│   │   │   └── plan.py              SheetRowPlanner — orchestrates above → SheetPlan
│   │   ├── applier/
│   │   │   └── apply_plan.py        (NEW) SheetPlan + CanonicalNameMap → list[PLI]
│   │   │                            100% deterministic, zero LLM calls (enforced by static test)
│   │   ├── validation/
│   │   │   ├── plan_invariants.py   (NEW) Tier 1 structural checks on SheetPlan
│   │   │   ├── plan_statistics.py   (NEW) Tier 2 statistical checks on SheetPlan
│   │   │   ├── source_cell_verifier.py    extraction validator (unchanged)
│   │   │   ├── header_match_verifier.py   extraction validator (unchanged)
│   │   │   ├── coverage_verifier.py       extraction validator (unchanged)
│   │   │   └── field_dropout_verifier.py  extraction validator (unchanged)
│   │   └── reconciler.py        merges workflow + validation outputs (lenient in V1)
│   │
│   ├── prompts/
│   │   ├── _shared.md           glossary + faithful-extraction principles
│   │   └── workflow/
│   │       ├── sheet_classifier.md  (unchanged)
│   │       ├── layout_hinter.md     (NEW)
│   │       ├── plan_reviewer.md     (NEW)
│   │       └── field_namer.md       (NEW)
│   │
│   ├── schemas/                 JSON schemas for LLM tool calls
│   │
│   └── interface/              FastAPI surface (lean in Spec 1; thicker in Spec 2)
│       ├── router.py           POST /extract, GET /health, GET /metrics
│       ├── interaction.py      request/response shapes
│       └── deps.py             provider injection
│
├── evals/                      ── INDEPENDENT — imports only models + ExtractorProtocol ──
│   ├── interface.py            ExtractorProtocol(workbook_path) -> ExtractionResult
│   ├── runner.py               run extractor over labeled corpus, collect per-file scores
│   ├── evaluator.py            per-file evaluation orchestration
│   ├── scorers/
│   │   ├── pli_recall.py
│   │   ├── field_precision_recall.py
│   │   ├── stage_recall.py
│   │   ├── source_cell_match.py        for each PLI, does source_cells[field] resolve to the value?
│   │   └── header_match.py             does each source column's header relate to the canonical field?
│   ├── matrix.py               render scoreboard (numbers only — no diff column)
│   ├── golden_snapshots/       frozen per-agent outputs (regression detection at agent level)
│   ├── labels -> ../../dataset/extracted/    (symlink to existing labels)
│   ├── workbooks -> ../../dataset/           (symlink to xlsx files)
│   └── runs/                   per-run JSON history
│
├── tests/
│   ├── unit/                   per-component, mocked LLM — sub-second, run on every commit
│   │                           includes apply_plan 3-axis cube tests + planner sub-component tests
│   ├── tools/                  per-tool with real workbook fixtures
│   └── integration/            end-to-end with real LLM, gated by TNA_RUN_LIVE_TESTS=1
│
├── scripts/
│   ├── run_eval.py             entrypoint for make eval
│   ├── refresh_golden.py       regenerate frozen agent snapshots
│   └── build-docker.sh
│
├── prometheus/
│   └── prometheus.yml          scrape config; targets api:8000/metrics
│
├── grafana/
│   ├── dashboards/json/        tna_extraction.json (latency p95, retries, validator failures, pli/file)
│   ├── dashboards/dashboards.yml
│   └── datasources/datasources.yml
│
└── docs/
    ├── architecture.md
    ├── adr/                    decision records
    └── runbook.md
```

## 5. Agent and component inventory

### 5.1 Planning pipeline (per sheet)

| Component | Kind | Single responsibility | Output |
|---|---|---|---|
| `SheetSurveyor` | deterministic | Collect observable sheet features | `SheetSignals` |
| `SheetRowPlanner` | deterministic | Classify every row; detect PLI mode, stage bands, KV anchors | `SheetPlan` (draft) |
| `validate_plan` T1 | deterministic | Structural invariants on SheetPlan | `Findings` (errors → re-plan) |
| `validate_plan` T2 | deterministic | Statistical sanity on SheetPlan | `Findings` (warnings → PlanReviewer) |
| `LayoutHinter` | LLM (conditional) | Resolve ambiguous layout regions | `LayoutHints` |
| `PlanReviewer` | LLM judge (conditional) | Accept or correct the SheetPlan | `PlanVerdict` |
| `FieldNamer` | LLM | Map raw header labels to canonical field names | `CanonicalNameMap` |
| `apply_plan` | deterministic | Resolve PLIs from SheetPlan + CanonicalNameMap | `list[PLI]` |

`SheetRowPlanner`, `SheetSurveyor`, `validate_plan`, and `apply_plan` are deterministic Python components. LLM agents (`LayoutHinter`, `PlanReviewer`, `FieldNamer`) follow `AgentSpec + AgentRunner`; prompts live in `app/prompts/workflow/<name>.md`. All LLM output is a Pydantic artifact (no free-form text). Retry-with-error-context (1 retry max) on validation failures.

**`apply_plan` determinism lock:** `apply_plan` and all its callees must not import `app.services.agents` or `app.services.llm_provider`. A static analysis test enforces this on every commit.

### 5.2 Workbook-level agents

| Component | Kind | Single responsibility | Output |
|---|---|---|---|
| `SheetClassifier` | LLM | Which sheets are TNA-relevant vs noise? | `relevant_sheets: list[str]` |

### 5.3 Extraction validation arm (4 deterministic checks)

| Check | Asks | V1 severity |
|---|---|---|
| `SourceCellVerifier` | For each PLI, does the cell at `source_cells[field]` actually contain the extracted value? | warn |
| `HeaderMatchVerifier` | For each canonical field's source column, does the header row contain text related to that field's vocabulary? | warn |
| `CoverageVerifier` | PLI count vs candidate-row count — flag when extracted < 80% of candidate-row count (configurable) | warn |
| `FieldDropoutVerifier` | Is any canonical field populated in <50% of PLIs? | warn |

All four are pure Python; no LLM. Each emits zero-or-more `ValidationFinding` records.

### 5.4 Removed in SheetRowPlanner migration

The following agents existed in the previous architecture and have been deleted:
`LayoutFingerprinter`, `BoundaryFinder`, `IdentityLocator`, `QuantityDateLocator`, `StageLocator`.
Their responsibilities are replaced by the deterministic `SheetRowPlanner` subsystem + the `FieldNamer` LLM agent.

## 6. Tool library

Tools are pure functions, registered with `@tool`. Each takes `WorkbookCtx` plus typed args, returns typed output (Pydantic). Grouped by purpose:

- **`survey`** — `list_sheets`, `workbook_summary`. Cheap, no cell reads.
- **`bulk_read`** — `peek_sheet`, `sample_rows`, `read_range`. Bounded windows.
- **`targeted`** — `read_row`, `read_relative`, `get_cell_at`. Single cell or row.
- **`structure`** — `get_merged_regions`, `count_non_empty_rows_in_column`.
- **`search`** — `find_value`.

Adding a tool is one file in `tools/<group>.py` with the decorator. Adding a tool category is a new file. The registry is automatic.

## 7. Pipeline definitions

The orchestrator (`app/services/extraction.py`) drives the pipeline in Python rather than a YAML DAG, because the conditional LLM-review branches (3b LayoutHinter, 3c PlanReviewer) and the validation-tier reaction loop are more naturally expressed as imperative code.

Per-sheet flow (pseudocode):

```python
signals   = SheetSurveyor(ctx, sheet)
plan      = SheetRowPlanner(signals)
findings  = validate_plan(plan, ctx)           # Tier 1 + Tier 2
if findings.has_errors:
    plan = SheetRowPlanner(signals, hints=findings.hints)   # re-plan
if needs_llm_review(plan, findings):
    hints   = LayoutHinter(signals)            # conditional LLM
    verdict = PlanReviewer(plan, hints, ctx)   # conditional LLM judge
    if verdict.needs_fix:
        plan = apply_corrections(plan, verdict)
name_map  = FieldNamer(plan)                   # LLM — 1 call per sheet
plis      = apply_plan(ctx, plan, name_map)    # 100% deterministic
```

Workbook-level aggregation then runs the 4 extraction validators over all sheets' PLIs and feeds the Reconciler.

Adding a new pipeline component = one file under `app/services/planner/` or `app/services/agents/`. No framework registration required.

## 8. Primary artifacts

| Artifact | Produced by | Consumed by | Shape |
|---|---|---|---|
| `SheetSignals` | `SheetSurveyor` | `SheetRowPlanner`, `LayoutHinter` | Merge map, header candidates, row density, vocab overlap |
| `RowSpec` | `SheetRowPlanner` | `validate_plan`, `apply_plan` | `idx`, `role`, `anchor_idx`, `group_id`, `sub_row_role` |
| `KVAnchor` | `SheetRowPlanner` | `apply_plan` | `label_cell`, `value_cell`, `field` |
| `StageBandSpec` | `SheetRowPlanner` | `apply_plan` | `name`, `sub_header_row`, `stage_cols`, `layout_mode` |
| `PliBlock` | `SheetRowPlanner` | `apply_plan` | `id`, `bbox`, `identity`, `stage_bands` |
| `SheetPlan` | `SheetRowPlanner` (+ reviewer corrections) | `validate_plan`, `FieldNamer`, `apply_plan` | `pli_mode`, `stage_scope`, `rows`, `pli_blocks`, `kv_anchors`, `stage_bands`, `confidence` |
| `LayoutHints` | `LayoutHinter` (conditional) | Re-plan pass | Mode suggestion + rationale |
| `PlanVerdict` | `PlanReviewer` (conditional) | Orchestrator correction loop | `verdict`, row corrections, warnings, confidence |
| `CanonicalNameMap` | `FieldNamer` | `apply_plan` | `{raw_label → canonical_field_name}` |

**Retired artifacts** (existed in prior architecture, no longer central): `StructuralFingerprint`, `PLIBoundaries`, `FieldMap`, `StageBandSet` (old shape with `BoundaryPattern` enum).

## 9. Reconciler logic (V1: lenient)

```python
def reconcile(workflow_out: WorkflowOutput,
              validation_out: ValidationFindings) -> ExtractionResult:
    """
    V1 contract:
      - workflow output passes through unchanged (no auto-drop)
      - each validation finding becomes a Warning attached to the relevant PLI / field
      - severity is informational unless any deterministic verifier reports
        a CRITICAL finding, in which case overall extraction_confidence is reduced
      - source_cells from workflow are preserved
    """
    result = workflow_out.to_extraction_result()
    for finding in validation_out:
        result.warnings.append(_finding_to_warning(finding))
    result.extraction_confidence = _aggregate(workflow_out, validation_out)
    return result
```

Strict mode (drop on validator failure) is a future config flag; not in V1.

## 10. Eval framework

### 10.1 Independent by contract

The eval module imports only `core/models.py` and an `ExtractorProtocol`:

```python
class ExtractorProtocol(Protocol):
    def extract(self, workbook_path: Path) -> ExtractionResult: ...
```

Any extractor that satisfies this — old `tna_parser/`, the new service, future rewrites — plugs in. Eval never knows which agents ran.

### 10.2 Scoring

For every labeled file in `dataset/extracted/`, runner computes:

| Metric | Definition |
|---|---|
| `pli_recall` | matched PLIs (by io_number/style/color tuple) / labeled PLIs |
| `field_precision` | correctly-valued canonical fields / extracted fields |
| `field_recall` | correctly-valued canonical fields / labeled fields |
| `stage_recall` | matched stages per matched PLI / labeled stages per matched PLI |
| `source_cell_match` | fraction of `source_cells` that round-trip to their cell value |
| `header_match` | fraction of source columns whose header relates to the canonical field |

Output is `evals/runs/<utc-timestamp>.json` and a console matrix (numbers only — no diff column).

### 10.3 Golden snapshots

Every workflow agent emits its output for each labeled file. Snapshots are committed under `evals/golden_snapshots/<file>/<agent>.json`. Tests compare current run to frozen snapshot; any drift surfaces *before* the full pipeline runs, isolating which agent changed.

Updating a snapshot is `make refresh-golden` (deliberate, reviewable).

### 10.4 Repeatability

- LLM temperature pinned at 0 for all workflow agents
- Snapshot tests are exact-match (Pydantic dump JSON, sorted keys, normalized whitespace)
- End-to-end eval over real LLM is rate-limited via `services/llm_provider.py` and budget-bounded per run
- Workbook reads are deterministic by construction

## 11. Telemetry (Spec 1, not deferred)

Per the decision to build telemetry from day 1:

**Metrics emitted:**
- `extraction_duration_seconds{file, format_detected}` — histogram
- `extraction_pli_count{file}` — gauge
- `agent_duration_seconds{agent}` — histogram, per-agent latency
- `agent_retry_count_total{agent, reason}` — counter
- `agent_token_input_total{agent, model}` / `agent_token_output_total{agent, model}` — counters
- `validator_findings_total{check, severity}` — counter
- `http_requests_total{method, endpoint, status}` — counter
- `llm_inference_duration_seconds{model}` — histogram

**Stack:** `prometheus_client` + `starlette-prometheus` middleware → `/metrics`. Prometheus scrapes the api service. Grafana ships a bootstrap dashboard with: extraction latency p95, retries per agent, validator failure rate, PLI count distribution, token cost per file.

All telemetry config is in `docker-compose.yml` from V1.

## 12. Config

`config/settings.py` uses `pydantic-settings`. Env files are layered:
- `.env.{APP_ENV}.local` (highest priority, gitignored)
- `.env.{APP_ENV}`
- `.env.local`
- `.env`

Required: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `APP_ENV`. Optional: `LOG_LEVEL`, `MAX_TOKENS`, `RETRY_LIMIT`, `TEMPERATURE`. Settings exposed as a typed singleton; no scattered `os.getenv`.

Environment values: `development | staging | production | test`. Environment-aware behavior baked in (e.g., production logs to stdout JSON, development logs human-readable).

## 13. Testing strategy

| Layer | What | When it runs |
|---|---|---|
| Unit (planner sub-components) | `row_classifier`, `block_segmenter`, `kv_anchor_detector`, `stage_band_detector` on synthetic fixtures covering all 6 observed layout families | Every commit, <2s total |
| Unit (plan validators) | Tier 1 + Tier 2 validators, both passing and failing cases for each invariant/statistic | Every commit |
| Unit (apply_plan 3-axis cube) | One test per `(pli_mode × stage_scope)` combination + sub_row_role variants; uses synthetic `SheetPlan` fixtures, no real LLM | Every commit |
| Unit (LLM agents) | `SheetClassifier`, `FieldNamer`, `LayoutHinter`, `PlanReviewer` with mocked LLM; assert artifact shape and decision logic | Every commit |
| Static analysis (apply_plan) | Assert `apply_plan` and callees do not import `agents` or `llm_provider` | Every commit |
| Tool tests | Each tool against real xlsx fixtures | Every commit |
| Snapshot tests | Per-agent golden snapshots compared to current | Every commit (when fixtures change → flagged) |
| Regression tests | CHRISTIAN BERG (3 → 7 PLIs) + new job-TNA (scattered KV + stacked sub-rows) must produce correct PLIs | Every commit |
| Integration | End-to-end with real LLM; gated by `TNA_RUN_LIVE_TESTS=1` | On demand / pre-merge |
| Eval | Full labeled corpus through real pipeline | Before merging any prompt or planner change |

The eval matrix is the gate that says "this change improves or regresses extraction".

For the full testing conventions — tiers, fixtures, failure-case patterns,
and the cookbook for adding new layouts — see [docs/TESTING.md](TESTING.md).

## 14. What's in V1 vs deferred

**V1 (Spec 1 — SheetRowPlanner pipeline):**
- Deterministic planning subsystem: `SheetSurveyor` + `SheetRowPlanner` + `validate_plan` (T1 + T2)
- Conditional LLM review: `LayoutHinter` + `PlanReviewer` (LLM-as-judge)
- `FieldNamer` LLM agent (vocabulary mapping)
- `apply_plan` — 100% deterministic, zero LLM calls, enforced by static analysis test
- `SheetClassifier` LLM agent (unchanged)
- 4 extraction validators + Reconciler (lenient)
- Full eval framework with label-driven scoring, golden snapshots, history JSONs
- 10 workbook tools in shared TOOL_REGISTRY
- Telemetry stack live (Prometheus + Grafana from `docker-compose up`)
- Structured logging
- FastAPI thin shell: POST /extract, GET /health, GET /metrics
- Single LLM provider (Anthropic)

**Deferred to Spec 2:**
- UI (xlsx upload + top/bottom JSON tabular view)
- Auth / rate-limiting full impl
- LLM circular fallback registry
- Strict-mode reconciler
- `FieldNamer` output caching across sheets within a workbook / across same-supplier workbooks

**Deferred to V2+ as needed:**
- DB persistence / memory
- New canonical fields / new layout patterns (additive — rules in `planner/` sub-components, no new enum cases required)
- Async/concurrent multi-file extraction

## 15. Migration plan

`tna_parser/` stays alive during V1 build. The new `tna-service/` is greenfield; no code moved from `tna_parser/` (only learnings and the labelled dataset are reused). When the eval matrix shows `tna-service` ≥ `tna_parser` on every labeled file, `tna_parser/` is archived.

## 16. Risks & open questions

| Risk | Mitigation |
|---|---|
| Planner heuristics wrong on a new unseen layout | Tier 1+2 validators + PlanReviewer catch planning errors before apply_plan; telemetry surfaces which planner rules fire most often |
| PlanReviewer fires too aggressively / drives up LLM cost | Tune confidence threshold via telemetry; current default 0.85 — reduce if median LLM calls/sheet stays acceptable |
| Snapshot tests too brittle when LLM output drifts despite temp=0 | Use semantic comparisons (Pydantic-aware) for tolerable drift; exact match only for structural fields |
| Telemetry adds dev-environment friction | Make Prometheus/Grafana opt-in via `make serve-with-telemetry`; default `make serve` is api-only |
| Eval becomes too slow once we have many labeled files | Parallelize the eval runner; cache LLM responses per (prompt-hash, model) for repeatability runs |

**V1 confidence aggregation:** simple weighted mean — `0.7 * mean(workflow_per_field_confidence) + 0.3 * (1 - validator_warn_rate)`. Calibration tuning is deferred to a V2 ADR once we have eval data showing whether the workflow's self-reported confidence correlates with correctness.

## 17. Success criteria

Spec 1 ships when:
1. `make eval` runs the full labeled corpus through the new service and prints the scoreboard matrix.
2. On the labeled subset of `dataset/extracted/` files, the new service matches or beats `tna_parser/` on `pli_recall`, `field_recall`, and `stage_recall`.
3. CHRISTIAN BERG regression test passes: 7 PLIs emitted with correct anchor/child structure.
4. new job-TNA regression test passes: 5 sheets each emit 1 PLI with full identity + 3 stage bands.
5. `docker compose up` brings up api + prometheus + grafana; the bootstrap dashboard shows live metrics during an extraction.
6. Adding a synthetic new field extractor (e.g., a `NotesExtractor` that captures the `Remarks` column) requires only: one file in `app/services/agents/`, one prompt in `app/prompts/workflow/` — no orchestrator changes.
7. Adding a synthetic new layout rule (e.g., diagonal KV anchors) requires only: rules in `planner/kv_anchor_detector.py` + one enum value if a new RowRole is needed — no changes to `apply_plan` or LLM agents.
8. `apply_plan` static analysis test passes: no imports of `agents` or `llm_provider` anywhere in the apply_plan call tree.

---

**Reviewers:** Nagasai
**Author:** Claude (this brainstorming session)
**Implementation plan:** to be written next via `superpowers:writing-plans`
