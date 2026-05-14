# TNA Service

> Multi-agent microservice that extracts structured PLI / Stage JSON from any TNA Excel file — regardless of supplier format — with deterministic validation, label-driven eval, and built-in observability.

```
                    POST /extract  ──►  ┌──────────────────────┐
   xlsx upload  ──────────────────────► │      TNA Service     │ ──► ExtractionResult JSON
                                        │  (FastAPI + Haystack)│      • PLIs + Stages
                                        └──────────────────────┘      • source_cells (traceability)
                                                                       • validation warnings
                                                                       • per-field confidence
```

## What it does

Given a TNA (Time-and-Action) workbook, the service identifies every Production Line Item (PLI) on the sheet(s), assigns canonical fields (`io_number`, `style_code`, `color_code`, `fabric_code`, `delivery_date`, `quantity`), extracts each production stage with its planned date, and returns a structured JSON envelope. Every extracted value carries the A1 address it was read from (`source_cells`) so a reviewer can verify any value at its source.

**It works across radically different TNA formats** (column-per-stage, vertical-merge multi-color, scattered key-value, stacked sub-tables, multi-band stage sections) by routing on _structural signals_ — not on supplier names.

## Why a microservice

- **Stateless** — each xlsx is independent. No DB.
- **Containerized** — `docker compose up` is the canonical run; the artifact is a Docker image, not a pip package.
- **Layered** — router / service / repository / model / enum, classic FastAPI layout.
- **Observable from day 1** — OpenTelemetry traces, metrics, and logs all flow into SigNoz.

For the architectural rationale and topology details, see [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## Quick start

```bash
# 0. From repo root:
cd tna-service

# 1. Create .env (copy the template, fill ANTHROPIC_API_KEY)
cp .env.example .env

# 2. Local install
make install
# This creates .venv/ and runs: pip install -e ".[dev]"

# 3. Run the service
make serve
# uvicorn at http://localhost:8000  (auto-reload on)

# 4. In another shell — extract a workbook:
curl -F "file=@path/to/your.xlsx" http://localhost:8000/extract | jq .

# 5. Or run the full Docker stack (api + SigNoz):
make up
# api       → http://localhost:8000
# SigNoz UI → http://localhost:8080
# OTLP gRPC → localhost:4317  (collector)
# OTLP HTTP → localhost:4318  (collector)
```

## Setting up on a fresh machine

Use this when cloning the repo onto a new laptop (e.g., a brand-new MacBook). For a returning environment, the Quick start above is enough.

### Prerequisites

- **Python 3.12** (Homebrew on macOS: `brew install python@3.12`; on Windows: the official installer).
- **Docker Desktop** (or any Docker engine that ships `docker compose`). On macOS: `brew install --cask docker`. Open the app once and let it finish first-time setup before running `make up`.
- **Git** + an `ANTHROPIC_API_KEY` (live tests and `/extract` need it).
- **GNU Make** — present on macOS by default; on Windows install via Git Bash / MSYS2 / Chocolatey.

### Steps

```bash
# 1. Clone + cd
git clone <repo-url> tna-service && cd tna-service

# 2. Create + activate the venv
python3.12 -m venv .venv
source .venv/bin/activate            # macOS / Linux
# or: .venv\Scripts\activate         # Windows (PowerShell)

# 3. Install deps (Makefile auto-detects the platform's venv layout)
make install

# 4. Configure environment
cp .env.example .env
# Edit .env and fill in ANTHROPIC_API_KEY at minimum.

# 5. Bring up the full stack (api + vendored SigNoz under deploy/)
make up

# 6. Verify
curl -s http://localhost:8000/health    # api healthy → 200
open http://localhost:8080              # SigNoz UI (Linux: xdg-open; Windows: start)
curl -F "file=@dataset/CHRISTIAN BERG- T&A.xlsx" http://localhost:8000/extract | jq .
# Wait ~30s, refresh SigNoz UI → Services tab → "tna-service" should appear.
```

### Optional — rehydrate Claude Code auto-memory

The repo ships a frozen snapshot of per-project auto-memory at [`docs/memory-snapshot/`](./docs/memory-snapshot/README.md) (rules, principles, dataset observations, baseline metrics — the opinionated layer Claude Code accumulates over a session). To re-import it into a fresh Claude Code install on the new machine, follow the slug-resolution instructions in that README. The repo-committed `CLAUDE.md` + `docs/JOURNEY.md` + `docs/PRINCIPLES.md` + `docs/adrs/` cover the same material in curated form, so this step is optional.

## Environment variables

All driven by `.env`. See [`.env.example`](./.env.example).

| Var | Required | Default | Description |
|---|---|---|---|
| `APP_ENV` | yes | `development` | One of `development` / `staging` / `production` / `test`. Drives env-file layering and JSON-vs-console log output. |
| `LOG_LEVEL` | no | `INFO` | Python logging level. |
| `ANTHROPIC_API_KEY` | yes (for `/extract`) | — | Anthropic API key. |
| `ANTHROPIC_MODEL` | no | `claude-sonnet-4-6` | Model identifier. |
| `MAX_TOKENS` | no | `4096` | Per-call output limit. |
| `TEMPERATURE` | no | `0.0` | Pinned at 0 for reproducible agent outputs. |
| `RETRY_LIMIT` | no | `1` | Per-agent retries on Pydantic schema validation failure. |

**Env-file layering** (highest priority first):
```
.env.{APP_ENV}.local  >  .env.{APP_ENV}  >  .env.local  >  .env
```

## HTTP API

### `POST /extract`
Upload an `.xlsx`, get structured PLIs.

**Request** — `multipart/form-data` with field `file` containing an xlsx.
**Response** — `application/json` matching `ExtractionResult`:

```json
{
  "plis": [
    {
      "io_number": "7000022459",
      "style_code": "DWJE MANOS 08 1000000052 5000006286",
      "color_code": "4139–NAVY TEAL",
      "fabric_code": "DIAGONAL FRENCH TERRY/100% ORGANIC COTTON/...",
      "delivery_date": "2026-05-19",
      "quantity": 1420,
      "stages": [
        { "name": "Sewing", "planned_date": "2026-04-23",
          "metadata": { "end_planned": "2026-04-27", "qty": 1420 } }
      ],
      "metadata": { "buyer": "MARC O'POLO INTERNATIONAL GMBH", ... },
      "source": {
        "sheet": "Sheet 1",
        "rows": [4],
        "cells": {
          "io_number": "K4",
          "style_code": "E4",
          "delivery_date": "P4"
        }
      },
      "confidence": { "io_number": 0.95, "style_code": 0.93, ... }
    }
  ],
  "warnings": [
    { "message": "field 'style_name' populated in 2/6 PLIs ...",
      "severity": "warning", "check": "field_dropout", "field": "style_name" }
  ],
  "format_detected": "vertical_merge",
  "extraction_confidence": 0.87,
  "source_file": "/tmp/upload.xlsx"
}
```

**Error responses:**
- `400` — upload missing or not `.xlsx`
- `500` — extraction failed (full exception in detail)

### `GET /health`
Liveness probe.
```json
{ "status": "healthy", "version": "0.1.0" }
```

---

## Make targets

| Target | What it does |
|---|---|
| `make install` | Creates `.venv/` and runs `pip install -e ".[dev]"` |
| `make test` | `pytest -q` — all unit + integration tests (live e2e tests are skipped by default) |
| `make test-live` | `TNA_RUN_LIVE_TESTS=1 pytest -m live -v` — runs e2e tests against the real Anthropic API |
| `make eval` | Runs the extractor over every labeled file in `dataset/extracted/`, prints scoreboard, writes a run JSON under `evals/runs/` |
| `make serve` | `uvicorn app.main:app --reload` |
| `make build` | `docker compose build` |
| `make up` | `docker compose up -d` (api + SigNoz stack) |
| `make down` | `docker compose down` |
| `make logs` | `docker compose logs -f api` |
| `make lint` | `ruff check app tests evals` |
| `make fmt` | `ruff format app tests evals` |
| `make clean` | Removes `.venv`, caches, coverage outputs |

---

## Project structure

The directory layout reflects a layered FastAPI microservice — router → service → repository → model — with each enum, prompt, agent, validator, and applier pattern living in its own file.

```
tna-service/
├── pyproject.toml          dependencies + ruff/pytest config
├── Makefile, Dockerfile, docker-compose.yml
├── .env.example, .python-version, .gitignore
│
├── app/                              ── all runtime code ──
│   ├── main.py                       FastAPI app: wires routers, middleware, telemetry
│   ├── config/settings.py            pydantic-settings + env layering
│   ├── enums/                        every Literal/Enum (Environment, CellDtype, PliMode, RowRole, StageScope, ...)
│   ├── models/                       pure domain — no I/O, no LLM
│   │   ├── workbook.py               Cell, MergedRegion, CellGrid, SheetMeta, WorkbookCtx
│   │   ├── extraction.py             PLI, Stage, ExtractionResult, Warning, FlexibleDate
│   │   └── artifacts.py              bridge schemas (fingerprint, boundaries, fieldmap, ...)
│   ├── schemas/                      API request/response shapes
│   ├── routers/                      HTTP layer — POST /extract, GET /health
│   ├── repositories/
│   │   ├── workbook_repo.py          register_workbook + cached handle
│   │   └── workbook_tools/           grouped read tools (@tool decorated)
│   │       ├── survey.py             list_sheets, workbook_summary
│   │       ├── bulk_read.py          peek_sheet, sample_rows, read_range
│   │       ├── targeted.py           read_row, read_relative, get_cell_at
│   │       ├── structure.py          get_merged_regions, count_non_empty_rows_in_column
│   │       └── search.py             find_value
│   ├── services/                     business logic
│   │   ├── extraction.py             top-level orchestrator
│   │   ├── llm_provider.py           LLMProvider Protocol + AnthropicProvider
│   │   ├── reconciler.py             lenient V1 merge (workflow + validation findings)
│   │   ├── planner/                  deterministic SheetRowPlanner pipeline
│   │   │   ├── sheet_surveyor.py     raw structural signals from the sheet
│   │   │   ├── row_classifier.py     per-row role assignment (HEADER/DATA/TOTAL/…)
│   │   │   ├── kv_anchor_detector.py key-value block identification (SHEET_IS_PLI layouts)
│   │   │   ├── stage_band_detector.py horizontal stage-band ranges
│   │   │   ├── block_segmenter.py    PLI block boundaries from classified rows
│   │   │   └── sheet_row_planner.py  assembles SheetPlan artifact
│   │   ├── agents/                   LLM agents — judge/label roles only
│   │   │   ├── _base.py              AgentSpec, AgentRunner, RetryPolicy, AgentRunFailure
│   │   │   ├── sheet_classifier.py
│   │   │   ├── layout_hinter.py      hints for the planner (LLM-as-advisor)
│   │   │   ├── plan_reviewer.py      LLM-as-judge: validates SheetPlan before apply
│   │   │   └── field_namer.py        maps supplier column headers → canonical field names
│   │   ├── validation/               4 deterministic checks (no LLM)
│   │   │   ├── source_cell_verifier.py
│   │   │   ├── header_match_verifier.py
│   │   │   ├── coverage_verifier.py     (80% floor)
│   │   │   └── field_dropout_verifier.py  (50% floor)
│   │   └── applier/                  deterministic — applies SheetPlan to workbook
│   │       └── apply_plan.py         apply_plan: ROW_PER_PLI / SHEET_IS_PLI / SECTION_PER_PLI
│   ├── prompts/                      .md prompts loaded by services/agents/
│   │   ├── _shared.md                glossary + faithful-extraction principles
│   │   └── workflow/                 one .md per workflow agent
│   └── core/                         cross-cutting
│       ├── logs.py                   structlog (JSON in prod)
│       ├── telemetry.py              OTel Metrics SDK (counters, histograms, gauges)
│       ├── middleware.py             RequestIdMiddleware (binds request_id to log context)
│       ├── prompt_loader.py
│       └── pipeline_loader.py
│
├── evals/                            ── INDEPENDENT — imports only app.models.* ──
│   ├── interface.py                  ExtractorProtocol (the contract)
│   ├── runner.py, evaluator.py, matrix.py
│   ├── scorers/                      pli_recall, field_precision_recall, stage_recall,
│   │                                 source_cell_match, header_match
│   └── runs/                         history JSON per `make eval` run
│
├── tests/
│   ├── unit/                         per-module, no fixture, sub-second
│   ├── flow/                         2+ deterministic functions chained, fixture-driven
│   ├── agent/                        single LLM agent + FakeLLM stub, fixture-driven
│   ├── e2e/                          full extract() + FakeLLM, fixture-driven
│   ├── live/                         real Anthropic API + real dataset (@pytest.mark.live)
│   └── fixtures/                     builders/ + expected/ — one xlsx scenario per file
│
├── deploy/docker/docker-compose.yaml   vendored SigNoz stack (pulled in via compose include:)
├── deploy/common/                      SigNoz support configs (clickhouse, signoz)
└── scripts/run_eval.py                 `make eval` entrypoint
```

---

## Testing

Five tiers, each with one job. **For the full conventions — fixture authoring,
expected.json shape, failure-case patterns, the cookbook for adding new
layouts — read [`docs/TESTING.md`](./docs/TESTING.md).**

| Tier | What it exercises | LLM | Fixture |
|---|---|---|---|
| `tests/unit/` | One function in isolation — enums, models, individual planner / applier / validator helpers, tools | none | inline (no fixture file) |
| `tests/flow/` | 2+ deterministic functions chained — e.g. `survey → row_classifier → segmenter → apply_plan` | none | per scenario |
| `tests/agent/` | One LLM agent under controlled inputs via `FakeLLM` stub | stub | per scenario |
| `tests/e2e/` | Full `extract()` pipeline with `FakeLLM` returning canned responses | stub | per scenario |
| `tests/live/` | Real Anthropic API against real `dataset/*.xlsx` — marked `@pytest.mark.live` | real | real dataset files |

```bash
make test                       # everything except live (~3s)
pytest tests -m live -q         # live tier — needs ANTHROPIC_API_KEY, run from an activated venv
make eval                       # full label scoreboard
```

### Adding a new test scenario

Two files, no test-code changes if a parametrized test in the right tier
already exists:

1. `tests/fixtures/builders/<name>.py` — a `build(wb)` function that
   populates a minimal workbook exhibiting the scenario.
2. `tests/fixtures/expected/<name>.json` — tier-keyed assertions
   (`layer_expectations.flow`, `layer_expectations.e2e`, …) plus an optional
   `failure_expectations` block for failure scenarios.

Then use `@fixture_case("<name>")` in your test (or add the name to an
existing parametrized test). The decorator handles xlsx materialization,
`WorkbookCtx` registration, expected.json parsing, and cache cleanup.

### What's enforced

- Function-scoped pytest fixtures → each test gets a fresh `tmp_path` + fresh
  `WorkbookCtx`. No state leakage.
- Fixture builders are Python modules — no xlsx binaries committed under
  `tests/fixtures/`. Files materialize per-test into `tmp_path`.
- Failure-case fixtures cover six categories: input validation, planner
  ambiguity, plan invariant violation, apply mismatch, agent failure
  (including irregular LLM responses — raise / wrong-type / missing-required /
  extra-fields), data anomaly.
- Negative assertions for every positive fixture confirm mode differentiation
  and absence of features that don't apply (e.g., a ROW_PER_PLI fixture must
  NOT emit `kv_anchors` or `pli_blocks`).
- `apply_plan` has a static AST guard (`tests/unit/applier/test_apply_plan_no_llm_imports.py`)
  ensuring it never imports `app.services.agents` or `app.services.llm_provider`.

The eval framework is separate from `tests/`. It treats the extractor as a
black box, imports only `app.models.*` and the `ExtractorProtocol` — see
[`ARCHITECTURE.md`](./ARCHITECTURE.md#eval-framework).

---

## Telemetry (SigNoz)

After `make up`, open **http://localhost:8080** and find `tna-service` under Services. From there you can pivot between:
- **Traces** — span tree per `/extract` call; click any span to see its attributes.
- **Logs Explorer** — filter by `trace_id`, `request_id`, `phase`, or `span_id`. These are attached as native OTel attributes on every log line (not just embedded in the body), so they are searchable and indexable.
- **Metrics** — RED metrics (rate, error rate, duration p50/p95/p99) are auto-generated from spans. The service map shows downstream call graphs.

SigNoz's built-in APM views cover what the old TNA Overview dashboard did (RED metrics, service map, exception tracker, log explorer, trace explorer). Custom dashboards can be authored later in SigNoz if needed.

For the full OTel pipeline details (TracerProvider + MeterProvider + LoggerProvider, metric names, propagator config), see [`ARCHITECTURE.md`](./ARCHITECTURE.md#telemetry).

---

## Adding things

Every common extension is a small contained change — typically one file plus one or two re-exports. See the [Extension points table in ARCHITECTURE.md](./ARCHITECTURE.md#extension-points) for the full matrix. Quick examples:

- **New workbook layout** → the `SheetRowPlanner` + `apply_plan` handle all three `PliMode` axes (ROW_PER_PLI, SHEET_IS_PLI, SECTION_PER_PLI) without new code; tweak `LayoutHinter` prompt if hinting is needed.
- **New canonical field** → one field on `PLI` (Pydantic) + one entry in the `FieldNamer` prompt vocabulary.
- **New agent** → one file under `app/services/agents/` + one prompt file under `app/prompts/workflow/`.
- **New validator** → one file under `app/services/validation/`.
- **New tool** → one `@tool`-decorated function under `app/repositories/workbook_tools/`.

The structural-layout acceptance tests in `tests/unit/structure/test_layout.py` enforce these conventions (one file per agent / validator / enum / tool group).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: app` | Not running from `tna-service/` or venv not activated | `cd tna-service` then activate the venv (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` on macOS/Linux) |
| `MissingAPIKey: ANTHROPIC_API_KEY is not set` | `.env` missing or key blank | `cp .env.example .env` and fill in your key |
| `/extract` returns 500 | Look at the response body and api logs (`make logs`) — usually a tool/agent exception |
| Tests in `tests/live/` all skipped | Default deselects `@pytest.mark.live` | `pytest tests -m live -q` from an activated venv (with `ANTHROPIC_API_KEY` set) |
| `make eval` says no labels found | `dataset/extracted/` doesn't exist inside `tna-service/` | This dir ships with the corpus; if missing, re-clone or restore from git |
| SigNoz UI empty after `/extract` | OTel batch processor flushes every ~15s; wait a moment, then refresh the Services or Traces view | —
| ClickHouse won't start | `signoz-net` is set up by the vendored compose include; check `docker compose logs clickhouse` for init errors | —

For any extraction-quality regression, the path is: run `make eval`, open `evals/runs/<timestamp>.json`, compare to a prior run. The `source_cells` and `warnings` arrays on each PLI tell you exactly where each value came from and what the validators flagged.

---

## License

See repository root.
