# TNA Service — Core Agentic Architecture + Eval Framework

> **Spec 1 of 2.** Covers the brain of a new microservice (`tna-service/`) that extracts structured PLI/Stage JSON from any TNA xlsx, plus the eval framework that gates every change to it. **Spec 2** (deferred) covers the service surface (FastAPI shape, the xlsx-upload UI with top/bottom JSON view, expanded ops tooling).

**Date:** 2026-05-12
**Status:** Draft for review
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
                              │ (Haystack Pipe)  │
                              └────────┬─────────┘
                                       │
                          ┌────────────┴────────────┐
                          ▼                         ▼
                  ┌───────────────┐         ┌───────────────┐
                  │   Workflow    │         │  Validation   │
                  │   (DAG)       │         │  (DAG)        │
                  ├───────────────┤         ├───────────────┤
                  │ SheetClassifr │         │ SourceCellVer │
                  │ LayoutFingerp │         │ HeaderMatchVer│
                  │ BoundaryFindr │         │ CoverageVer   │
                  │ IdentityLoc.  │         │ DropoutVer    │
                  │ QtyDateLocatr │         │               │
                  │ StageLocator  │         │ (deterministic)│
                  │ Applier       │         │               │
                  └───────┬───────┘         └───────┬───────┘
                          │                         │
                          └────────────┬────────────┘
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

The two arms run in parallel against the same workbook. **Workflow** induces locations and applies them. **Validation** independently asks "does this extraction match what the workbook actually says?" — all deterministic in V1. The **Reconciler** merges the two: workflow output passes through, validator findings attach as warnings. Nothing is auto-dropped in V1 — strict mode lives behind a future config flag.

### 2.2 Orchestration phases (detailed)

The orchestrator drives seven phases. Each phase has a domain-anchored purpose; the failure modes we've already seen in the dataset shape what each phase emits and how it falls back.

**Phase 0 — Ingest** *(deterministic)*. Open xlsx via openpyxl into a cached `WorkbookCtx`. Compute initial workbook summary (sheet names, dims, file size).

**Phase 1 — Sheet Classification** *(LLM, parallel across sheets)*. For each sheet, `SheetClassifier` decides "TNA-relevant or noise?". Catches GUESS-style summary/lab/log sheets. Output: `relevant_sheets: list[str]`.

**Fast-path branch.** After Phase 2 on the first relevant sheet, if the fingerprint signals `sheets_appear_parallel`, the orchestrator runs `BoundaryFinder` to confirm pattern = `one_sheet_per_pli`. If so, Phases 2–5 run **once** on the representative sheet and the Applier iterates `sheet_iter` (cross-sheet handled inside the applier). This is the structural fix for the NEW.xlsx 5×5=25-PLI duplication class — no post-hoc break needed.

**Per-sheet loop (or once, if one_sheet_per_pli):**

**Phase 2 — Fingerprint** *(LLM, per sheet)*. `LayoutFingerprinter` emits `StructuralFingerprint` (9 booleans + `stage_layout_mode` + `sample_evidence`). Retry once with error context on schema failure. Hard fail → halt this sheet with a warning.

**Phase 3 — Boundary** *(LLM, per sheet, depends on fingerprint)*. `BoundaryFinder` emits `PLIBoundaries` (pattern ∈ {`one_row_per_pli`, `one_sheet_per_pli`, `vertical_merge`, `data_then_total`} + data range + grouping columns + optional total-row indicator). The agent sees the **full** merged-regions list (50-cap), a top-10 peek, and mid+last sample rows. Domain rule: when multiple merge groups exist in the grouping column, `data_end_row` spans **all** of them (this is the CHRISTIAN BERG fix). Retry 1× with error context; on hard fail → default `one_row_per_pli` boundary + warn.

**Phase 4 — Locators** *(LLM, parallel within sheet — 3-wide)*. All three locators consume `PLIBoundaries` only; they're independent. Run in parallel:
- `IdentityLocator` — io_number, style_code, color_code, fabric_code. Header-text rules (header text wins, not column position; "Buyer Po No" → io_number; corrupted headers don't shift alignment). This is the MOPD FW26 fix.
- `QuantityDateLocator` — quantity, delivery_date. For `vertical_merge`, sees merge-witness rows so it can pick the split (per-PLI) quantity column over the aggregate column. This is the Compass Pro multi-color fix.
- `StageLocator` — `StageBandSet` with sub_columns canonicalization (`L/D send` + `L/D appl` → one `L/D` stage), multi-band emission (Pre-Production / Fabric / Production for 63261-style).

Field/Stage maps merge and metadata is **deduplicated** against stage sub_columns (so `Sewing Qty` doesn't appear in both `Stage.metadata.qty` AND `PLI.metadata.sewing_qty`). Per-agent retry 1×; partial failure → empty FieldMap part → Applier handles gracefully.

**Phase 5 — Apply** *(deterministic)*. Pattern-dispatched via registry (`one_row_per_pli` → iterate `[start..end]`; `data_then_total` → iterate + drop indicator-matching rows; `vertical_merge` → iterate all rows + propagate merge anchors; `one_sheet_per_pli` → iterate `sheet_iter`, cross-sheet inside the applier).

Pre-loop: collect `header_values_above_data` per canonical-field column (this is the NORTHERN REFLECTIONS fix for stacked sub-tables). Per row: read fields (with merge propagation when `vertical_merge`); if any field value equals a known header label → strip identity; construct PLI tolerantly (drop fields that fail `FlexibleDate`). Filter: `is_real_pli` (canonical identity required). Stages applied against the same row list with merge propagation. Emit `source_cells: {field → A1 address}` on every PLI.

**Phase 6 — Validation** *(deterministic, 4 checks in parallel)*. Once all sheets are aggregated:
- `SourceCellVerifier` — for each PLI, does the cell at `source_cells[field]` still contain the extracted value?
- `HeaderMatchVerifier` — for each canonical field's source column, does the header text contain canonical-field vocabulary?
- `CoverageVerifier` — extracted PLI count vs candidate-row count in the boundary range; flags below 80% (this would have caught MAIN FALL KIDS #1's 80 → 2 silent loss).
- `FieldDropoutVerifier` — canonical fields populated in <50% of PLIs.

Output: `list[ValidationFinding]` with severity `info | warn`.

**Phase 7 — Reconcile** *(deterministic)*. Workflow output passes through unchanged. Validation findings become Warnings attached to the result. `extraction_confidence = 0.7 · mean(workflow_per_field_confidence) + 0.3 · (1 − validator_warn_rate)`. `source_cells` preserved on every PLI.

### 2.3 Locked orchestration decisions

| # | Decision | Locked choice | Rationale |
|---|---|---|---|
| D1 | Per-sheet parallelism in Phases 2–5 | **Sequential V1**, max-concurrency knob deferred | Most labeled files are 1–3 sheets; Anthropic rate-limit risk; simpler error handling |
| D2 | Within-sheet locator parallelism | **All 3 locators in parallel** | All three consume `PLIBoundaries` only; independent outputs; ~3× faster Phase 4 |
| D3 | Fast-path for `one_sheet_per_pli` | **Yes, branch after fingerprint** when `sheets_appear_parallel=True` | Eliminates NEW.xlsx duplication class structurally |
| D4 | Validation timing | **After all sheets aggregated** (Phase 6) | Cross-sheet context available to verifiers; simpler than per-sheet validation merge |
| D5 | Retry policy | **1 retry with error context**, uniform across LLM agents | DKN session showed retry-with-context fixes Anthropic's JSON-as-string artifact reliably |
| D6 | Agent failure handling | **Tiered**: Fingerprinter fail → halt sheet; Boundary fail → default + warn; Locator fail → empty + warn; Applier fail → never (log if it does) | Matches `tna_parser/pipeline.py` patterns; partial output is more useful than no output |
| D7 | Adaptive routing on fingerprint | **No skip-list V1** — all 6 workflow agents always run | Today's agents are universal; skip-optimisation deferred until eval shows waste |
| D8 | Cross-sheet PLI aggregation | **Concatenate**, preserve `source_sheet` on every PLI, no dedup | Different sheets genuinely hold different PLIs (GUESS master files); dedup would mask data |
| D9 | Phase 5 determinism gates | **Both** `is_real_pli` AND repeat-header detection | Each catches a different class of false-PLI (NORTHERN REFLECTIONS + totals-row) |
| D10 | Telemetry granularity | **Per-phase + per-agent histograms; per-validator counters; per-file gauges** (PLI count, retry count, cost) | Lets us correlate prompt changes to specific agent/phase behavior in Grafana |

These ten are locked by review; revisiting any of them requires an ADR.

## 3. Incremental Adaptability Contract

This is the headline NFR. Every axis a new TNA family can differ along has a dedicated additive extension point.

| New thing arrives | What you change | What you do NOT touch |
|---|---|---|
| New layout shape (e.g. `horizontal_merge`, `multi_section`) | Add entry to `BoundaryPattern` enum + one handler in `applier/patterns/<name>.py` (registry-dispatched) | All agents, validators, eval, orchestrator |
| New canonical field on `PLI` | Add Pydantic field + one line in `IdentityLocator` or new sibling locator agent | All existing extraction; eval auto-picks the field up if labels include it |
| New non-PLI row pattern | Add a deterministic check in `agents/validation/` | Workflow agents |
| New supplier header vocabulary | Add term to a data-only vocab table (not code) | All agents |
| New tool | One `@tool`-decorated function in `tools/` | Agents that don't need it |
| New agent | One file in `agents/workflow/` or `agents/validation/` + one `connect()` line in pipeline YAML | All other agents; orchestrator code |
| New labeled file with no rules changed | Drop JSON in `dataset/extracted/` | Anything else |

A PR that touches more than two columns above gets a yellow flag in code review.

**Enforcement primitives:**
- Pattern dispatch via registry (decorator-based)
- Haystack Pipelines defined in YAML, not Python `if` chains
- `tools/` are pure functions, `@tool`-registered
- Pydantic models use `extra="ignore"` so additive schema changes don't break old labels
- Eval runner discovers labeled files at runtime

## 4. Directory layout

New microservice at `F:\DAITA\ARENA\TNA\tna-service\` (greenfield — `tna_parser/` stays as fallback during rollout).

```
tna-service/
├── pyproject.toml              uv-managed; haystack-ai, fastapi, pydantic, anthropic, openpyxl,
│                               pydantic-settings, structlog, prometheus-client, starlette-prometheus
├── Makefile                    make eval / test / serve / build / lint / fmt
├── Dockerfile
├── docker-compose.yml          api + prometheus + grafana (telemetry from day 1)
├── .env.example                ANTHROPIC_API_KEY, ANTHROPIC_MODEL, APP_ENV, LOG_LEVEL, ...
├── .python-version
│
├── src/tna_service/
│   ├── config/
│   │   └── settings.py         pydantic-settings; env-layered .env.{APP_ENV}.local > .env.{APP_ENV} > .env
│   │
│   ├── core/                   pure domain — no I/O, no LLM
│   │   ├── models.py           PLI, Stage, ExtractionResult, Warning
│   │   ├── workbook.py         WorkbookCtx, Cell, MergedRegion
│   │   └── artifacts.py        bridge schemas — FieldMap, FieldLocation,
│   │                           PLIBoundaries, StageBandSet, ValidationFindings
│   │
│   ├── tools/                  Haystack-compatible tool functions, grouped by purpose
│   │   ├── _registry.py        @tool decorator + registry
│   │   ├── survey.py           list_sheets, workbook_summary
│   │   ├── bulk_read.py        peek_sheet, sample_rows, read_range
│   │   ├── targeted.py         read_row, read_relative, get_cell_at
│   │   ├── structure.py        get_merged_regions, count_non_empty_rows_in_column
│   │   └── search.py           find_value
│   │
│   ├── agents/
│   │   ├── _base.py            AgentSpec, RetryPolicy, shared types
│   │   ├── prompts/            all prompts as .md, loaded by helpers
│   │   │   ├── workflow/       sheet_classifier.md, layout_fingerprinter.md, boundary_finder.md,
│   │   │   │                   identity_locator.md, quantity_date_locator.md, stage_locator.md
│   │   │   └── _shared.md      glossary + faithful-extraction principles
│   │   ├── workflow/
│   │   │   ├── sheet_classifier.py        TNA-relevant vs noise
│   │   │   ├── layout_fingerprinter.py    StructuralFingerprint
│   │   │   ├── boundary_finder.py         PLIBoundaries (pattern + range/segments)
│   │   │   ├── identity_locator.py        io_number, style_code, color_code, fabric_code
│   │   │   ├── quantity_date_locator.py   quantity, delivery_date
│   │   │   └── stage_locator.py           StageBandSet
│   │   └── validation/         all deterministic in V1
│   │       ├── source_cell_verifier.py    cell at source_cells[field] still contains the value
│   │       ├── header_match_verifier.py   column header contains canonical-field-related text
│   │       ├── coverage_verifier.py       PLI count vs row count in boundary; flags low coverage
│   │       └── field_dropout_verifier.py  <50% population for a canonical field
│   │
│   ├── pipelines/
│   │   ├── workflow.yaml       DAG: SheetClassifier → LayoutFingerprinter → BoundaryFinder →
│   │   │                       (IdentityLocator ‖ QuantityDateLocator ‖ StageLocator) → Applier
│   │   ├── validation.yaml     DAG: 4 verifiers run in parallel on the workflow output
│   │   └── orchestrator.py     composes both arms; calls Reconciler
│   │
│   ├── reconciler/
│   │   └── reconciler.py       merges workflow + validation outputs (lenient in V1)
│   │
│   ├── applier/
│   │   ├── _registry.py        BoundaryPattern → handler registry
│   │   ├── field_applier.py    apply_field_map (deterministic)
│   │   ├── stage_applier.py    apply_stage_band_set (deterministic)
│   │   └── patterns/           one file per pattern handler
│   │       ├── one_row_per_pli.py
│   │       ├── one_sheet_per_pli.py
│   │       ├── vertical_merge.py
│   │       └── data_then_total.py
│   │
│   ├── services/
│   │   └── llm_provider.py     LLMProvider Protocol + AnthropicProvider (single-provider V1)
│   │
│   ├── interface/              FastAPI surface (lean in Spec 1; thicker in Spec 2)
│   │   ├── router.py           POST /extract, GET /health, GET /metrics
│   │   ├── interaction.py      request/response shapes
│   │   └── deps.py             provider injection
│   │
│   ├── system/                 cross-cutting
│   │   ├── logs.py             structured logging (structlog) — JSON output with run_id correlation
│   │   ├── telemetry.py        Prometheus collectors + setup_metrics(app)
│   │   ├── middleware.py       request id, structured access log
│   │   └── rate_limit.py       slot only — full impl in Spec 2
│   │
│   └── utils/
│       ├── pipeline_loader.py  load Haystack Pipeline from YAML
│       └── prompt_loader.py    load .md prompt with frontmatter
│
├── evals/                      ── INDEPENDENT — imports only core/models + ExtractorProtocol ──
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
│   ├── unit/                   per-agent, mocked LLM — sub-second, run on every commit
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

## 5. Agent inventory

### 5.1 Workflow arm (6 agents)

| Agent | Single decision | Output |
|---|---|---|
| `SheetClassifier` | Which sheets are TNA-relevant? | `relevant_sheets: list[str]` |
| `LayoutFingerprinter` | What structural patterns describe each sheet? | `StructuralFingerprint` |
| `BoundaryFinder` | What's the PLI organization for this sheet? | `PLIBoundaries` (pattern + data range + optional skip_segments) |
| `IdentityLocator` | Which columns hold io_number / style_code / color_code / fabric_code? | `FieldMap.locations[identity]` |
| `QuantityDateLocator` | Which columns hold quantity and delivery_date? | `FieldMap.locations[qty,date]` + metadata_locations |
| `StageLocator` | Which columns form stage bands, canonical names, sub_columns? | `StageBandSet` |

All workflow agents are Haystack Components. Prompt lives in `agents/prompts/workflow/<name>.md`. Output is a Pydantic artifact (no free-form text). Retry-with-error-context (1 retry max) on validation failures.

### 5.2 Validation arm (4 deterministic checks)

| Check | Asks | V1 severity |
|---|---|---|
| `SourceCellVerifier` | For each PLI, does the cell at `source_cells[field]` actually contain the extracted value? | warn |
| `HeaderMatchVerifier` | For each canonical field's source column, does the header row contain text related to that field's vocabulary? | warn |
| `CoverageVerifier` | PLI count vs candidate-row count in the boundary range — flag when extracted < 80% of candidate-row count (configurable) | warn (this would have caught MAIN FALL KIDS #1's 80 → 2 silent loss) |
| `FieldDropoutVerifier` | Is any canonical field populated in <50% of PLIs? | warn |

All four are pure Python; no LLM. Each emits zero-or-more `ValidationFinding` records.

### 5.3 Not in V1

- `FieldReviewer` (LLM-based second opinion). Skipped until deterministic checks demonstrably leave gaps. Documented in `docs/adr/` as a deferred decision.

## 6. Tool library

Tools are pure functions, registered with `@tool`. Each takes `WorkbookCtx` plus typed args, returns typed output (Pydantic). Grouped by purpose:

- **`survey`** — `list_sheets`, `workbook_summary`. Cheap, no cell reads.
- **`bulk_read`** — `peek_sheet`, `sample_rows`, `read_range`. Bounded windows.
- **`targeted`** — `read_row`, `read_relative`, `get_cell_at`. Single cell or row.
- **`structure`** — `get_merged_regions`, `count_non_empty_rows_in_column`.
- **`search`** — `find_value`.

Adding a tool is one file in `tools/<group>.py` with the decorator. Adding a tool category is a new file. The registry is automatic.

## 7. Pipeline definitions

Both arms are Haystack Pipelines declared in YAML. Example shape (illustrative — real YAML follows Haystack 2.x format):

```yaml
# pipelines/workflow.yaml
components:
  sheet_classifier:      { type: SheetClassifier }
  layout_fingerprinter:  { type: LayoutFingerprinter }
  boundary_finder:       { type: BoundaryFinder }
  identity_locator:      { type: IdentityLocator }
  quantity_date_locator: { type: QuantityDateLocator }
  stage_locator:         { type: StageLocator }
  applier:               { type: Applier }
connections:
  - { from: sheet_classifier.relevant_sheets, to: layout_fingerprinter.sheets }
  - { from: layout_fingerprinter.fingerprint, to: boundary_finder.fingerprint }
  - { from: boundary_finder.boundaries,       to: identity_locator.boundaries }
  - { from: boundary_finder.boundaries,       to: quantity_date_locator.boundaries }
  - { from: boundary_finder.boundaries,       to: stage_locator.boundaries }
  - { from: identity_locator.field_map,       to: applier.field_map_parts }
  - { from: quantity_date_locator.field_map,  to: applier.field_map_parts }
  - { from: stage_locator.stage_band_set,     to: applier.stage_band_set }
```

`orchestrator.py` loads both pipelines, runs them, hands results to the reconciler. Adding an agent = new file + 1-2 connection lines.

## 8. Reconciler logic (V1: lenient)

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

## 9. Eval framework

### 9.1 Independent by contract

The eval module imports only `core/models.py` and an `ExtractorProtocol`:

```python
class ExtractorProtocol(Protocol):
    def extract(self, workbook_path: Path) -> ExtractionResult: ...
```

Any extractor that satisfies this — old `tna_parser/`, the new service, future rewrites — plugs in. Eval never knows which agents ran.

### 9.2 Scoring

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

### 9.3 Golden snapshots

Every workflow agent emits its output for each labeled file. Snapshots are committed under `evals/golden_snapshots/<file>/<agent>.json`. Tests compare current run to frozen snapshot; any drift surfaces *before* the full pipeline runs, isolating which agent changed.

Updating a snapshot is `make refresh-golden` (deliberate, reviewable).

### 9.4 Repeatability

- LLM temperature pinned at 0 for all workflow agents
- Snapshot tests are exact-match (Pydantic dump JSON, sorted keys, normalized whitespace)
- End-to-end eval over real LLM is rate-limited via `services/llm_provider.py` and budget-bounded per run
- Workbook reads are deterministic by construction

## 10. Telemetry (Spec 1, not deferred)

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

## 11. Config

`config/settings.py` uses `pydantic-settings`. Env files are layered:
- `.env.{APP_ENV}.local` (highest priority, gitignored)
- `.env.{APP_ENV}`
- `.env.local`
- `.env`

Required: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `APP_ENV`. Optional: `LOG_LEVEL`, `MAX_TOKENS`, `RETRY_LIMIT`, `TEMPERATURE`. Settings exposed as a typed singleton; no scattered `os.getenv`.

Environment values: `development | staging | production | test`. Environment-aware behavior baked in (e.g., production logs to stdout JSON, development logs human-readable).

## 12. Testing strategy

| Layer | What | When it runs |
|---|---|---|
| Unit (per-agent) | Each agent in isolation with mocked LLM; assert artifact shape and decision logic on canned inputs | Every commit, <2s total |
| Tool tests | Each tool against real xlsx fixtures | Every commit |
| Snapshot tests | Per-agent golden snapshots compared to current | Every commit (when fixtures change → flagged) |
| Integration | End-to-end with real LLM; gated by `TNA_RUN_LIVE_TESTS=1` | On demand / pre-merge |
| Eval | Full labeled corpus through real pipeline | Before merging any prompt change |

The eval matrix is the gate that says "this change improves or regresses extraction".

## 13. What's in V1 vs deferred

**V1 (Spec 1):**
- 6 workflow agents + 4 deterministic validators + reconciler (lenient)
- Haystack pipeline orchestration via YAML
- Full eval framework with label-driven scoring, golden snapshots, history JSONs
- Tools reorganized into 5 groups
- Applier with pattern registry (one_row_per_pli, one_sheet_per_pli, vertical_merge, data_then_total)
- Telemetry stack live (Prometheus + Grafana from `docker-compose up`)
- Structured logging
- FastAPI thin shell: POST /extract, GET /health, GET /metrics
- Single LLM provider (Anthropic)

**Deferred to Spec 2:**
- UI (xlsx upload + top/bottom JSON tabular view)
- Auth / rate-limiting full impl
- LLM circular fallback registry
- `FieldReviewer` LLM agent
- Strict-mode reconciler

**Deferred to V2+ as needed:**
- DB persistence / memory
- New canonical fields / new layout patterns (as new TNA families surface)
- Async/concurrent multi-file extraction

## 14. Migration plan

`tna_parser/` stays alive during V1 build. The new `tna-service/` is greenfield; no code moved from `tna_parser/` (only learnings and the labelled dataset are reused). When the eval matrix shows `tna-service` ≥ `tna_parser` on every labeled file, `tna_parser/` is archived.

## 15. Risks & open questions

| Risk | Mitigation |
|---|---|
| Haystack 2.x Pipeline expressiveness for our DAG | Prototype the workflow pipeline first; fall back to Python-composed components if YAML proves limiting |
| Snapshot tests too brittle when LLM output drifts despite temp=0 | Use semantic comparisons (Pydantic-aware) for tolerable drift; exact match only for structural fields |
| Telemetry adds dev-environment friction | Make Prometheus/Grafana opt-in via `make serve-with-telemetry`; default `make serve` is api-only |
| Eval becomes too slow once we have many labeled files | Parallelize the eval runner; cache LLM responses per (prompt-hash, model) for repeatability runs |

**V1 confidence aggregation:** simple weighted mean — `0.7 * mean(workflow_per_field_confidence) + 0.3 * (1 - validator_warn_rate)`. Calibration tuning is deferred to a V2 ADR once we have eval data showing whether the workflow's self-reported confidence correlates with correctness.

## 16. Success criteria

Spec 1 ships when:
1. `make eval` runs the full labeled corpus through the new service and prints the scoreboard matrix.
2. On the labeled subset of `dataset/extracted/` files, the new service matches or beats `tna_parser/` on `pli_recall`, `field_recall`, and `stage_recall`.
3. `docker compose up` brings up api + prometheus + grafana; the bootstrap dashboard shows live metrics during an extraction.
4. Adding a synthetic new agent (e.g., a `NotesExtractor` that captures the `Remarks` column) requires only: one file in `agents/workflow/`, one prompt in `agents/prompts/workflow/`, and one connection line in `pipelines/workflow.yaml` — no other code touched. This is the incremental-adaptability acceptance test.
5. Adding a synthetic new boundary pattern (e.g., `horizontal_merge`) requires only: one enum value + one handler file under `applier/patterns/` — no other code touched.

---

**Reviewers:** Nagasai
**Author:** Claude (this brainstorming session)
**Implementation plan:** to be written next via `superpowers:writing-plans`
