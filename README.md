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
- **Observable from day 1** — Prometheus collectors per agent and per validator; Grafana dashboard pre-provisioned.

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

# 5. Or run the full Docker stack (api + Prometheus + Grafana):
make up
# api      → http://localhost:8000
# prom     → http://localhost:9090
# grafana  → http://localhost:3000   (anon viewer, "TNA Extraction" dashboard)
```

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
      "source_sheet": "Sheet 1",
      "source_rows": [4],
      "source_cells": {
        "io_number": "K4",
        "style_code": "E4",
        "delivery_date": "P4"
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

### `GET /metrics`
Prometheus exposition. See [`ARCHITECTURE.md`](./ARCHITECTURE.md#telemetry) for the collector list.

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
| `make up` | `docker compose up -d` (api + Prometheus + Grafana) |
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
│   ├── enums/                        every Literal/Enum (Environment, CellDtype, BoundaryPattern, ...)
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
│   │   ├── extraction.py             top-level orchestrator (Phases 0–7)
│   │   ├── llm_provider.py           LLMProvider Protocol + AnthropicProvider
│   │   ├── reconciler.py             lenient V1 merge (workflow + validation findings)
│   │   ├── agents/                   one file per workflow agent
│   │   │   ├── _base.py              AgentSpec, AgentRunner, RetryPolicy, AgentRunFailure
│   │   │   ├── sheet_classifier.py
│   │   │   ├── layout_fingerprinter.py
│   │   │   ├── boundary_finder.py
│   │   │   ├── identity_locator.py
│   │   │   ├── quantity_date_locator.py
│   │   │   └── stage_locator.py
│   │   ├── validation/               4 deterministic checks (no LLM)
│   │   │   ├── source_cell_verifier.py
│   │   │   ├── header_match_verifier.py
│   │   │   ├── coverage_verifier.py     (80% floor)
│   │   │   └── field_dropout_verifier.py  (50% floor)
│   │   └── applier/                  deterministic — applies artifacts to workbook
│   │       ├── _registry.py          BoundaryPattern → handler registry
│   │       ├── field_applier.py      apply_field_map (incl. merge-prop + repeat-header strip)
│   │       ├── stage_applier.py      apply_stage_band_set + strip_stage_columns_from_metadata
│   │       └── patterns/             one file per BoundaryPattern handler
│   ├── prompts/                      .md prompts loaded by services/agents/
│   │   ├── _shared.md                glossary + faithful-extraction principles
│   │   └── workflow/                 one .md per workflow agent
│   └── core/                         cross-cutting
│       ├── logs.py                   structlog (JSON in prod)
│       ├── telemetry.py              Prometheus collectors
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
│   ├── unit/                         per-module, fast, mocked LLM
│   ├── repositories/                 per-tool with real workbook fixtures
│   └── integration/                  end-to-end (gated by TNA_RUN_LIVE_TESTS=1)
│
├── scripts/run_eval.py               `make eval` entrypoint
├── prometheus/prometheus.yml
└── grafana/{datasources,dashboards}  bootstrap dashboard provisioned at start
```

---

## Testing

Three layers:

| Layer | What | When it runs |
|---|---|---|
| **Unit** (`tests/unit/`) | One module at a time. LLM mocked. Sub-second. | Every commit |
| **Repository** (`tests/repositories/`) | Workbook-tool functions against real xlsx fixtures from `dataset/` | Every commit |
| **Integration** (`tests/integration/`) | End-to-end orchestrator against real Anthropic API on labeled files. Gated by `TNA_RUN_LIVE_TESTS=1`. | On demand / pre-merge |

```bash
make test          # everything except live (sub-second on a quiet machine)
make test-live     # the 5 e2e regression guards (one per known-tricky layout family)
make eval          # full label scoreboard — every labeled file in dataset/extracted/
```

The eval framework treats the extractor as a black box. It imports only `app.models.*` and the `ExtractorProtocol` — see [`ARCHITECTURE.md`](./ARCHITECTURE.md#eval-framework).

---

## Telemetry

The api emits Prometheus metrics from `/metrics`. The pre-provisioned Grafana dashboard (TNA folder → "TNA Extraction — overview") shows:
- **Extraction latency p95** by `format_detected`
- **Agent retries** per minute by agent
- **Validator findings** per minute by check + severity
- **PLIs per file** time series

For the full collector list (and which code path emits each one), see [`ARCHITECTURE.md`](./ARCHITECTURE.md#telemetry).

---

## Adding things

Every common extension is a small contained change — typically one file plus one or two re-exports. See the [Extension points table in ARCHITECTURE.md](./ARCHITECTURE.md#extension-points) for the full matrix. Quick examples:

- **New workbook layout** → one enum entry in `app/enums/boundary_pattern.py` + one handler in `app/services/applier/patterns/<name>.py`.
- **New canonical field** → one field on `PLI` (Pydantic) + one line in `IdentityLocator` or a new sibling locator.
- **New agent** → one file under `app/services/agents/` + one prompt file under `app/prompts/workflow/`.
- **New validator** → one file under `app/services/validation/`.
- **New tool** → one `@tool`-decorated function under `app/repositories/workbook_tools/`.

The acceptance tests in `tests/integration/test_acceptance_extensibility.py` enforce these conventions structurally.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: app` | Not running from `tna-service/` or venv not activated | `cd tna-service && .venv/Scripts/activate` (Windows) / `source .venv/bin/activate` (Linux) |
| `MissingAPIKey: ANTHROPIC_API_KEY is not set` | `.env` missing or key blank | `cp .env.example .env` and fill in your key |
| `/extract` returns 500 | Look at the response body and api logs (`make logs`) — usually a tool/agent exception |
| Tests in `tests/integration/` all skipped | `TNA_RUN_LIVE_TESTS` not set | `set -a && . ./.env && set +a && TNA_RUN_LIVE_TESTS=1 pytest -m live` |
| `make eval` says no labels found | `dataset/extracted/` doesn't exist inside `tna-service/` | This dir ships with the corpus; if missing, re-clone or restore from git |
| Prometheus says target down | api container not yet healthy | `docker compose logs api` |

For any extraction-quality regression, the path is: run `make eval`, open `evals/runs/<timestamp>.json`, compare to a prior run. The `source_cells` and `warnings` arrays on each PLI tell you exactly where each value came from and what the validators flagged.

---

## License

See repository root.
