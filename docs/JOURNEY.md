# TNA Service — Journey

## Why this doc

This captures how we got here so the next session doesn't relearn from scratch. It is a narrative arc, not a technical reference. For current technical state see `CLAUDE.md` + `ARCHITECTURE.md`. For the rules that emerged from this work see `docs/PRINCIPLES.md`. For major architectural decisions see `docs/adrs/`.

---

## Phase 0 — The problem (pre-2026-05-07)

### What TNA spreadsheets look like

TNA (Time and Action) spreadsheets are production milestone trackers used by garment buyers and factories. Each file tracks one or more PLIs (Product Line Items — a style-color-quantity combination) through a sequence of stages (Cutting, Sewing, Washing, Inspection, Ex Factory, etc.), with planned and actual dates per stage.

The challenge: there is no standard format. Six distinct layout families were identified in the dataset:

1. **Orders Plan** — one PLI per sheet, sheets named by Job No. Scattered KV pairs for identity (Job No, Quantity, dates). Three stacked stage bands (`Pre-Production TNA`, `Fabric TNA`, `Production TNA`) with TALL_SUB_ROWS (Plan/Action/Deviation as rows, not columns). Files: `63261-TNA.xlsx`, `new job-TNA.xlsx`, `NEW.xlsx`, `TNA DETAILS.xlsx`.
2. **DKN columnar 2-row header** — single sheet, ~40 cols, 2-row stage headers, WIDE_SUB_COLUMNS (Plan/Actual/Approved as columns). File: `20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx`.
3. **Compass Pro / Marc O'Polo columnar** — single sheet, ~38 cols, ~60 merged regions, multi-row header with buyer/season title row. ~6 files. Variant of DKN columnar — both are tabular with multi-row headers; differences are in column conventions.
4. **Christian Berg vertical-merge** — one logical PLI = N visual rows (one per color), 46 merged regions. File: `CHRISTIAN BERG- T&A.xlsx`.
5. **Flat with TOTAL footers** — each PLI = data row + `TOTAL` row beneath. File: `FA26 YC & EUROPE T&A #1.xlsx`.
6. **Master file with noise sheets** — multi-sheet workbook where only one sheet is the actual TNA; others are sample tracking / SKU maps. Files: GUESS ATHLEISURE and MAIN FALL series. Often 1000+ rows in the main sheet.

### Why off-the-shelf parsing fails

Standard tabular parsers (pandas, openpyxl row iteration) assume uniform tabular structure. Merged cells, multi-row headers, stacked stage bands, and scattered KV blocks all break this assumption. The field names and stage column conventions differ per supplier. A format-name lookup table (`if filename contains "DKN"`) breaks on every unseen supplier.

### Why we built this

Daita Labs processes TNAs at volume for garment industry clients. Manual extraction is slow and error-prone. The goal: a format-agnostic AI parser that extracts structured PLI JSON from any TNA Excel file, with traceable source cells and production-quality reliability.

---

## Phase 1 — tna_parser: single-prompt baseline (2026-05-09)

The first working system was `tna_parser`, a standalone Python experiment package (not this repo). It used a single Anthropic API call: send a full sheet grid via tool use, receive a complete `ExtractionResult`.

The M0 baseline ran live against the DKN file (3 PLIs, 6 stages each) using `claude-sonnet-4-6`.

**v1 results (initial prompt):**
- PLI recall: 100%
- Field precision/recall: 71%
- Stage recall: 83%

**Key failure modes:**
- Model split `style_code` at the first numeric token (`"890162 TAVIRA_2 522148"` → two fields). Cross-PLI copy errors also appeared.
- Model emitted `"Sewing Start"` + `"Sewing End"` as two stages instead of one `"Sewing"` stage — even with explicit prompt instructions.
- Model embedded per-field confidence objects (`{value, confidence}`) despite the tool schema expecting flat values — causing 24 Pydantic validation errors.

**The faithful-extraction pivot (v2, 2026-05-09):**

Rewriting the system prompt to encode four principles — copy verbatim, one cell one field, null over fabrication, two PLIs may share io_number — recovered field precision/recall to 100%. Stage recall held at 83%. The stage miss was attributed to fundamental single-prompt limitations: a focused Stage Locator agent would do better.

**v2 results:**
- PLI recall: 100%
- Field precision/recall: 100%
- Stage recall: 83%

**tna_parser at completion:** 66 unit/integration tests (later cited as 72 in memory files; exact count at close of M0 was 66 offline tests plus the live baseline run). The package included: `models.py`, `workbook.py`, `tools.py`, `anthropic_client.py`, `baseline.py`, `eval.py`, `cli.py`.

**What broke:** The single-prompt approach could not handle layout variance. One prompt could not reliably do boundary detection (row arithmetic), stage canonicalization, and field extraction simultaneously for six different layout families. The multi-agent split became the next step.

---

## Phase 2 — Multi-agent experiment (pre-Spec1, brainstorm 2026-05-07)

The brainstorm on 2026-05-07 established the three-pillar architecture (see `docs/adrs/0001-multi-agent-split.md`):

1. **Multi-agent specialists** — narrow input, narrow output, independently testable.
2. **Structural-signal routing** — orchestrator routes on shape signals, never on format/supplier names.
3. **Induction-then-apply** — LLM induces extraction rules from a sample; Python applies deterministically.

A multi-agent version of `tna_parser` was built as an experiment (27 tasks), implementing: `LLMProvider Protocol`, `@tool decorator` + `ToolRegistry`, 4 specialist agents (Inspector, PLI Boundary Finder, Field Locator, Stage Locator), bridge artifacts (`FieldMap`, `StageBandSet`, `PLIBoundaries`), deterministic appliers.

Key results from live runs: the `BoundaryFinder` agent on CHRISTIAN BERG returned 3 PLIs (correct: 7). This was the first signal that LLM-based row arithmetic was fundamentally unreliable — a lesson that would drive the SheetRowPlanner design.

---

## Phase 3 — Microservice scaffold: Spec1 (2026-05-12 to 2026-05-13)

The `tna-service` repo (this repo) was created to productionise the multi-agent approach as a proper microservice (~40 tasks, commits starting 2026-05-12 22:03 IST).

**What was built:**
- FastAPI service with `POST /extract`, `GET /health`
- Layered architecture: `app/core/`, `app/models/`, `app/repositories/`, `app/services/`, `app/routers/`
- Pydantic settings with env layering (`Environment` enum, `.env` support)
- `structlog` structured JSON logging + `RequestIdMiddleware`
- Initial Prometheus telemetry (`prometheus_client` API)
- 10 `@tool`-decorated workbook tools: `list_sheets`, `workbook_summary`, `peek_sheet`, `sample_rows`, `read_range`, `read_row`, `read_relative`, `get_cell_at`, `get_merged_regions`, `find_value`
- `LLMProvider` Protocol + `AnthropicProvider` with `$ref` inlining for nested Pydantic schemas
- `AgentSpec + AgentRunner` with retry-with-error-context
- 6 agents: `SheetClassifier`, `LayoutFingerprinter`, `BoundaryFinder`, `IdentityLocator`, `QuantityDateLocator`, `StageLocator`
- Pattern registry + 4 pattern handlers for `BoundaryPattern` dispatch
- `field_applier` + `stage_applier` (deterministic) consuming bridge artifacts
- 4 validators: `SourceCellVerifier`, `HeaderMatchVerifier`, `CoverageVerifier` (80% floor), `FieldDropoutVerifier` (50% floor)
- Reconciler (lenient V1)
- Eval harness: 5 scorers (pli_recall, field_pr, stage_recall, source_cell_match, header_match), matrix renderer, `make eval`
- Dockerfile + docker-compose (api + Prometheus + Grafana)

**At close of Spec1:** approximately 154 tests passing. The BoundaryFinder/LayoutFingerprinter/etc. agents were present but the CHRISTIAN BERG 3-vs-7 PLI bug persisted.

---

## Phase 4 — Nested Source refactor (4 tasks, between Spec1 and SRP)

The `source_cells` field on extracted values was initially flat (a list at the PLI level). Downstream consumers needed source traceability per field and per stage value. The refactor moved `source` into a nested structure under each PLI field value and each Stage value.

All validators, the extraction orchestrator, eval scorers, and tests were updated. The canonical label schema (`dataset/extracted/*.json`) uses the nested form: `quantity` (not `order_quantity`) with a nested `source` dict. This was a breaking schema change that required updating every layer.

---

## Phase 5 — SheetRowPlanner (2026-05-13, ~30 tasks)

This was the biggest architectural shift. See `docs/adrs/0003-sheet-row-planner.md` for the full decision context.

**Root cause of the change:** `BoundaryFinder` returned 3 PLIs for CHRISTIAN BERG (correct: 7). Row arithmetic — counting rows, grouping by anchor cells, detecting total rows — is exactly what LLMs are poor at. The existing `BoundaryPattern` enum (4 values) covered only 4 points in a much larger layout space.

**The induction-then-apply architecture:**

Deterministic components (`SheetSurveyor`, `row_classifier`, `kv_anchor_detector`, `stage_band_detector`, `block_segmenter`) produce a `SheetPlan` artifact. LLM agents (`LayoutHinter`, `PlanReviewer`, `FieldNamer`) review and refine it conditionally. `apply_plan` executes 100% deterministically with zero LLM calls.

**`SheetPlan` — the unified artifact:**
- PLI scope: `ROW_PER_PLI` | `SECTION_PER_PLI` | `SHEET_IS_PLI`
- Stage scope: `SHEET_LEVEL` | `SECTION_LOCAL` | `PLI_LOCAL`
- PLI height: via `RowSpec.sub_row_role` (`PLAN`, `ACTION`, `DEVIATION`)

**Validation tiers:**
- Tier 1: structural invariants (ReferenceIntegrity, RowUniqueness, HeaderContiguity, etc.) — mandatory, det
- Tier 2: statistical sanity (SequenceMatch, TotalArithmetic, DateBandDensity, etc.) — mandatory, det
- Tier 3: PlanReviewer (LLM judge, conditional)

**LLM-as-judge rule:** det wins on disagreement; LLM failure is non-blocking.

**Results:**
- CHRISTIAN BERG: 7 PLIs (was 3).
- Orders Plan family (new job-TNA, etc.): all sheets produce 1 PLI each via `SHEET_IS_PLI` + `TALL_SUB_ROWS` stage bands.
- LLM call count per sheet: ~1-2 median (was ~5).

**Deleted in this phase:** `LayoutFingerprinter`, `BoundaryFinder`, `IdentityLocator`, `QuantityDateLocator`, `StageLocator` agents; `field_applier`, `stage_applier`; pattern handlers; `BoundaryPattern` and `StageLayoutMode` enums.

**Docs updated at end of phase:** `ARCHITECTURE.md`, `docs/SPEC.md`, `README.md`, the SheetRowPlanner design doc Status flipped to Implemented.

---

## Phase 6 — Test strategy overhaul (2026-05-13, ~29 tasks)

Before this phase: ~154 tests, inconsistent mechanics, sparse failure coverage, smoke-only agent tests, no written conventions. See `docs/adrs/0004-test-strategy.md` for the decision.

**What changed:**
- Five-tier taxonomy: `unit / flow / agent / e2e / live`
- Fixture pattern: `tests/fixtures/builders/<name>.py` + `tests/fixtures/expected/<name>.json`
- `FixtureCase` dataclass + `@fixture_case` decorator for parametrize sugar
- `FakeLLM` stub keyed by output schema name
- 6 positive fixture anchors: `tabular_simple`, `tabular_with_totals`, `tabular_repeat_header`, `sheet_per_pli_clean`, `row_per_pli_with_merges`, `section_per_pli_two_blocks`
- 6 failure fixture anchors: `workbook_only_title_row`, `tabular_corrupt_no_identity_col`, `plan_invariant_dangling_anchor`, `apply_name_map_missing_required`, `agent_returns_invalid_json`, `stage_band_low_date_density`
- Reorganised: `tests/regression/` + `tests/integration/test_e2e_live.py` → `tests/live/`; acceptance + repositories tests → `tests/unit/`
- Rewrote composite tests as fixture-driven flow tests; agent tests as FakeLLM-driven behaviour tests
- `docs/TESTING.md` codifying all conventions

**Test count at close:** ~209 passing (non-live). Full conventions at `docs/TESTING.md`.

---

## Phase 7 — Telemetry buildout (2026-05-13, ~7 milestones)

Built in sequence, each landing as an independent commit group:

1. **Token counters + tool counter + phase timing** — `agent_tokens_input/output` from Anthropic `resp.usage`; per-tool invocation counter via `@tool` decorator; per-phase timing histogram + `phase` field in log context.
2. **Depth metrics** — `extractions_total{status}`, `agent_calls_total{agent, status}`, `llm_calls_total{model, status}`, `tool_duration_seconds`, `tool_errors_total`.
3. **Grafana dashboards** — TNA Overview (5-row structured layout: headlines, calls, failures, tokens, duration heatmaps); TNA Logs dashboard.
4. **Loki + Promtail** — log aggregation with Loki datasource + Logs panel in Grafana. Discovered Promtail file-mount issues on Docker Desktop (needed an override file); Grafana variable-substitution edge cases (pinned UIDs, regex patterns).
5. **PLIs counter** — `plis_extracted_total` cumulative PLI count.
6. **Structured logging coverage** — structured log events across 17 previously-silent modules (orchestrator, planner, applier, validators, agents, tools).
7. **OTel tracing** — OTel SDK init + manual spans (extract/phase/agent/llm); Tempo backend; Loki derivedFields → Tempo pivot; W3C + B3 TraceContext propagation; httpx auto-instrumentation for outgoing LLM calls. Lazy OTel imports + noop tracer so tests pass without OTel locally.

At the end of Phase 7, the stack was: api + Prometheus + Loki + Promtail + Tempo + Grafana (6 containers, 3 custom dashboards, 3 storage backends). This worked but was operationally heavy.

---

## Phase 8 — SigNoz migration (2026-05-13 to 2026-05-14, ~22 tasks)

See `docs/adrs/0005-signoz-migration.md` for the full decision. Short version: 5 Grafana-stack products collapsed to SigNoz Community Edition — single UI, single ClickHouse backend, single OTel push path.

**Three phases:**

**Phase 1 (app code migration):** `prometheus_client` → OTel Metrics SDK in `telemetry.py`; `MeterProvider` + `LoggerProvider` wired in `tracing.py`; drop `/metrics` route; drop `starlette_prometheus`. Tests still pass (209).

**Design deviation 1 — log pipeline:** the design proposed an OTel `LoggingHandler` on the stdlib root logger. This silently no-oped: structlog uses `PrintLoggerFactory`, which bypasses stdlib entirely. Fix: a custom structlog processor `emit_to_otel_logs` in `app/core/tracing.py` pushes events directly through the OTel SDK's global `LoggerProvider`. Stdout JSON is unchanged.

**Phase 2 (compose swap):** initial implementation authored custom SigNoz config files (`signoz/clickhouse-config.xml`, `signoz/otel-collector-config.yml`) and added the 4 SigNoz services directly to `docker-compose.yml`. This ran into ClickHouse `remote_servers` hostname alignment issues.

**Design deviation 2 — SigNoz architecture model:** the design was written against pre-v0.113 SigNoz (separate `query-service` + `frontend` images, separate `signoz-schema-migrator`). SigNoz v0.113.0 (2026-02-25) deprecated the schema-migrator and unified `query-service` + `frontend` into a single `signoz/signoz` binary on port 8080.

**Design deviation 3 — config ownership:** instead of maintaining custom SigNoz config files, the implementation vendors SigNoz's upstream `deploy/` tree under `deploy/` in this repo and pulls it in via Docker Compose `include:`. This gets schema bootstrap (`signoz-telemetrystore-migrator`) for free and eliminates config drift. Commit `bc11324`.

**Phase 3 (cleanup + docs):** deleted `grafana/`, `prometheus/`, `loki/`, `promtail/`, `tempo/` config directories. Updated `README.md`, `ARCHITECTURE.md`, `docs/SPEC.md`. Commit `0f4a607`.

**Stack at close:** api + clickhouse + otel-collector + signoz (5 containers, 0 custom dashboards, 1 ClickHouse backend, 1 config directory under `deploy/`). All three signals queryable at `localhost:8080`.

**One open item:** SZ Task 22 — final end-to-end verification with SigNoz UI confirming traces, metrics, and logs all flowing from a live `/extract` call.

---

## What's next

Open items as of 2026-05-14, pulled from memory + plan files. Not a roadmap — things that have been named but not done:

- **SZ Task 22**: Final end-to-end SigNoz verification (triggered `/extract` → traces in Traces tab, RED metrics in Services tab, logs filterable by `request_id`).
- **Custom SigNoz dashboards**: re-create TNA Overview-style 5-row layout in SigNoz's dashboard builder. Deferred pending confirmation that SigNoz defaults suffice.
- **SigNoz alerting**: email/Slack/PagerDuty integration for extraction failure rate. Out of scope for v1.
- **Reverse-proxy auth on SigNoz UI**: Community Edition has no built-in auth. Add nginx/Caddy proxy if needed.
- **FieldNamer caching**: cache `CanonicalNameMap` output across sheets from the same supplier within a workbook. Deferred from SheetRowPlanner design.
- **PLI count sanity confidence tuning**: `PlanReviewer` fires at confidence < 0.85. This threshold should be iterated based on telemetry data from real runs.
- **Labels for remaining layout families**: Orders Plan (family 1), Christian Berg (family 4), FA26 TOTAL footers (family 5) are not yet labeled in `dataset/extracted/`. These are needed for eval coverage across all six families.
- **PLAN Final code review**: the original tna_parser code review (task #22) was deferred and never completed. Not blocking on tna-service, but worth a pass over the early Spec1 code.
