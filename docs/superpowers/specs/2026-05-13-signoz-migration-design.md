# SigNoz migration — design

**Date:** 2026-05-13
**Status:** Approved, ready for implementation plan

## Problem

The TNA service's observability is currently built on the Grafana ecosystem: Prometheus (metrics), Loki + Promtail (logs), Tempo (traces), Grafana (UI). This works, but it's five products with four config directories, three storage backends, and three custom dashboards. Each piece has its own query language, its own retention model, and its own failure modes (we recently spent a session debugging Promtail's file-mount behaviour on Docker Desktop and Grafana's variable-substitution edge cases). The mental cost of "where do I look for X?" is high.

The user wants a single platform for metrics + logs + traces, one UI, fewer moving parts.

## Goal

Replace the Grafana stack (Prometheus + Loki + Promtail + Tempo + Grafana) with SigNoz Community Edition. Use OpenTelemetry as the only telemetry-emission path from the application. Single UI, single backend (ClickHouse), single config directory.

## Non-goals

- Changing app extraction behaviour. All 209 tests must still pass throughout.
- Re-authoring custom dashboards in v1. SigNoz's auto-generated APM views (service map, RED metrics, exception tracker, log explorer, trace explorer) cover ~80% of what we use today. Custom dashboards can be added later as needed.
- Switching to a managed/cloud observability backend. SigNoz Community Edition is self-hosted, same as our current setup.
- Adding new metrics or events. Same observable surface, different transport.

## Design

### End-state architecture

```
   POST /extract  ──► api ──┬─► OTel traces  ──► OTLP gRPC ─┐
                            ├─► OTel metrics ──► OTLP gRPC ─┤
                            └─► OTel logs    ──► OTLP gRPC ─┤
                                                            │
                                                            ▼
                                              ┌─────────────────────┐
                                              │   otel-collector    │
                                              └──────────┬──────────┘
                                                         │ ClickHouse exporter
                                                         ▼
                                              ┌─────────────────────┐
                                              │     clickhouse      │
                                              │  (single backend)   │
                                              └──────────┬──────────┘
                                                         │
                                                         ▼
                                              ┌─────────────────────┐
                                              │ signoz-query-service│ ◄── SigNoz Frontend
                                              └─────────────────────┘     (localhost:3301)
```

Everything from the app travels over one OTLP gRPC connection carrying three streams (traces, metrics, logs). The OTel Collector fans out to ClickHouse via three exporter types. No file-tailing, no Docker log driver, no Prometheus scrape.

### Container footprint

| | Today | After SigNoz |
|---|---|---|
| Services | 6 (api + prometheus + loki + promtail + tempo + grafana) | 5 (api + clickhouse + otel-collector + signoz-query + signoz-frontend) |
| Config dirs | 5 (prometheus/, loki/, promtail/, tempo/, grafana/) | 1 (signoz/) |
| Custom dashboards | 3 (TNA Overview, TNA Logs, TNA Extraction) | 0 (SigNoz defaults) |
| Named volumes | 3 (loki-data, tempo-data, grafana — implicit) | 2 (clickhouse-data, signoz-data) |
| Backends to query | 3 (Prom, Loki, Tempo) | 1 (ClickHouse via SigNoz) |
| Query languages | 3 (PromQL, LogQL, TraceQL) | 1 (SigNoz UI + raw ClickHouse SQL fallback) |

### Application code changes

**`app/core/telemetry.py`** — full rewrite using OTel Metrics SDK. Today:
```python
agent_calls_total = Counter("agent_calls_total", "...",
                            labelnames=("agent", "status"))
agent_calls_total.labels(agent="sheet_classifier", status="success").inc()
```
After:
```python
_meter = metrics.get_meter(__name__)
agent_calls_total = _meter.create_counter(
    "agent_calls_total", description="Total agent invocations.")
agent_calls_total.add(1, {"agent": "sheet_classifier", "status": "success"})
```
Same names, same semantics. Labels become attributes passed at call time. Histograms switch from `.observe(x)` to `.record(x, attrs)`. Gauges become `create_observable_gauge()` (callback-based) or `create_up_down_counter()`. ~150 lines rewritten in `telemetry.py`.

**~30 call sites updated** across `app/services/extraction.py`, `app/services/agents/_base.py`, `app/services/llm_provider.py`, `app/repositories/workbook_tools/_registry.py`. Mechanical search-and-replace from prometheus_client API to OTel API.

**`app/core/tracing.py`** — extend `configure_tracing()` to set up:
- `MeterProvider` + `PeriodicExportingMetricReader` + `OTLPMetricExporter` (every 15s push interval)
- `LoggerProvider` + `BatchLogRecordProcessor` + `OTLPLogExporter`
- Existing `TracerProvider` + OTLPSpanExporter unchanged
- Function returns the LoggerProvider so `logs.py` can attach a stdlib handler to it

**`app/core/logs.py`** — add `attach_otel_log_handler(logger_provider)` that registers an OTel `LoggingHandler` on the stdlib root logger. structlog already routes through stdlib `logging.getLogger(name)`, so every structlog event flows through this handler and becomes an OTel `LogRecord` with trace_id/span_id auto-attached.

**`app/main.py`** — drop `starlette_prometheus` import, `PrometheusMiddleware`, and the `/metrics` route. Call `attach_otel_log_handler(...)` after `configure_tracing(...)` returns.

**`pyproject.toml`** — remove `prometheus-client` and `starlette-prometheus`. OTel SDK packages stay (already added during the Tempo work).

### Compose changes

Add:
- `clickhouse` (image: `clickhouse/clickhouse-server:24.1.2-alpine`, single-node, health-checked)
- `otel-collector` (image: `signoz/signoz-otel-collector:0.111.7`, listens on 4317 gRPC + 4318 HTTP)
- `signoz-query-service` (image: `signoz/query-service:0.55.0`, backed by ClickHouse)
- `signoz-frontend` (image: `signoz/frontend:0.55.0`, UI at port 3301)
- Named volumes: `clickhouse-data`, `signoz-data`

Remove:
- `prometheus`, `loki`, `promtail`, `tempo`, `grafana` (5 service blocks)
- Volumes: `loki-data`, `tempo-data`
- The `docker-compose.override.yml.example` (Loki Docker driver workaround) — no longer needed

Update `api` service environment:
- Remove `TEMPO_OTLP_ENDPOINT`
- Add `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`, `OTEL_SERVICE_NAME=tna-service`

### Config files

**`signoz/clickhouse-config.xml`** — minimal single-node ClickHouse config, ~30 lines, taken from SigNoz's official compose example.

**`signoz/otel-collector-config.yml`** — receivers (OTLP gRPC + HTTP), processors (batch + resourcedetection), exporters (clickhousetraces, clickhousemetricswrite, clickhouselogsexporter). Three pipelines: traces, metrics, logs.

### Migration order

Three phases, each landable as an independent commit set:

**Phase 1 — Application code migration**
Replace `prometheus_client` with OTel Metrics SDK, add LoggerProvider, attach OTel log handler, drop `/metrics` endpoint and Prometheus middleware. ~200 lines net change across 6 files. Tests still pass. Between Phase 1 and 2 metrics/logs push to the Tempo endpoint which doesn't accept them — transient observability gap, extraction continues working.

**Phase 2 — Compose swap**
Atomic: add 4 SigNoz services + 2 config files, remove 5 Grafana-stack services + 4 config dirs (deletion deferred to Phase 3 for rollback safety), update api environment to `OTEL_EXPORTER_OTLP_ENDPOINT`. After this commit, the full observability stack is operational on SigNoz.

**Phase 3 — Cleanup and docs**
Delete `grafana/`, `prometheus/`, `loki/`, `promtail/`, `tempo/` config directories. Delete `docker-compose.override.yml.example`. Update `README.md`, `ARCHITECTURE.md`, `docs/SPEC.md` to point at the new stack. Flip this design doc's `Status` to `Implemented`.

### Verification per phase

| Phase | Verifies |
|---|---|
| 1 | `pytest tests -q -m "not live"` → 209 passed; `grep -rn "prometheus_client\|starlette_prometheus" app/` → zero matches; `/metrics` returns 404 |
| 2 | `docker compose up -d` clean; SigNoz UI loads at `localhost:3301`; triggered `/extract` shows in Services tab with RED metrics; trace ID from response header opens span tree; log filter by `request_id` shows full event chain; ClickHouse direct query confirms data ingestion |
| 3 | No references to removed services in repo (outside `docs/superpowers/`); `make up/down/logs` work; README + ARCHITECTURE describe SigNoz only |

### Rollback

Each phase is a clean `git revert` away. Phase 2 + 3 revert restores the entire Grafana stack from git. Data accumulated in SigNoz's ClickHouse during trial is lost on `docker compose down -v` — same model as before with Tempo/Loki/Prom volumes.

### Trade-offs

**Gain**: single UI, service map auto-built, exception tracker, APM defaults, lower mental footprint, no Docker log-driver fragility, one config directory.

**Lose**: 3 custom Grafana dashboards (defaults cover most use cases), some panel customization power (SigNoz dashboards are less expressive than Grafana), higher resource floor (~1.5GB RAM for ClickHouse vs ~500MB for full Grafana stack).

**Keep**: all app behaviour, all 209 tests, `request_id` propagation, OTel trace IDs, structured JSON logging, eval framework.

### Known caveats

1. OTel Python Logs SDK is in `opentelemetry.sdk._logs` (underscore prefix marks it as provisional, though widely used). Worth pinning a version range in `pyproject.toml`.
2. ClickHouse cold start takes ~30s. `signoz-query-service` waits via `depends_on: condition: service_healthy`.
3. SigNoz Community Edition has no built-in auth — matches our current Grafana anonymous-viewer setup. Reverse proxy if needed later.
4. `prometheus-client` may persist as a transitive dep of `opentelemetry-instrumentation-fastapi` and similar — direct dependency is removed; transitives are immaterial.

## Acceptance criteria

- All 209 unit/integration tests pass after each phase.
- `docker compose up -d` brings up: api + clickhouse + otel-collector + signoz-query-service + signoz-frontend (5 containers).
- `localhost:3301` shows SigNoz UI with `tna-service` listed under Services.
- A `/extract` request appears in the Services tab within 30s, with auto-generated RED metrics, traces, and logs all queryable.
- Trace ID from the response header opens the span tree in SigNoz Traces; clicking any span pivots to logs filtered to that span's request.
- `grep -rn "prometheus_client\|starlette_prometheus\|/metrics" app/ tests/` → zero non-historical matches.
- README, ARCHITECTURE, SPEC docs describe the new stack only.
- This design doc's Status is flipped to `Implemented`.

## Open questions deferred to the implementation plan

- Exact ClickHouse version: pinning `24.1.2-alpine` for v1; can upgrade later.
- Whether to keep the Grafana JSON dashboards in `docs/superpowers/` as historical artifacts or delete them entirely. Plan defaults to deletion (clean repo); user can override.
- Custom SigNoz dashboards to recreate later (TNA Overview-style 5-row layout). Deferred — see if SigNoz defaults suffice first.
- SigNoz alerting rules (email/Slack/PagerDuty integration) — out of scope for v1.
