# 0005 — SigNoz migration

**Date:** 2026-05-13 (design); 2026-05-14 (implemented)
**Status:** Accepted

## Context

The TNA service's observability was built on the Grafana ecosystem: Prometheus (metrics), Loki + Promtail (logs), Tempo (traces), Grafana (UI). This is five products with four config directories, three storage backends, and three custom dashboards. During development we spent a session debugging Promtail file-mount behaviour on Docker Desktop and Grafana's variable-substitution edge cases.

More concretely:
- Traces went to Tempo; metrics went to Prometheus; logs went to Loki. "Where do I look for X?" required knowing which product for which signal.
- Promtail's log pipeline required a Docker Desktop log driver override and complex label filters.
- No single-pane UI for all three signals.

The user wanted: one platform, one UI, fewer moving parts.

## Decision

Replace the Grafana stack (Prometheus + Loki + Promtail + Tempo + Grafana) with SigNoz Community Edition. Use OpenTelemetry as the only telemetry-emission path from the application. Single UI, single backend (ClickHouse), single config directory.

**Application changes:**
- `app/core/telemetry.py`: rewritten from `prometheus_client` API to OTel Metrics SDK. Same metric names and semantics; labels become attributes.
- `app/core/tracing.py`: extended `configure_tracing()` to set up `MeterProvider` + `LoggerProvider` alongside the existing `TracerProvider`. All three push to the OTLP endpoint.
- Log pipeline: the design proposed an OTel `LoggingHandler` on the stdlib root logger. This silently no-oped because structlog uses `PrintLoggerFactory`, which bypasses stdlib entirely. The fix: a custom structlog processor `emit_to_otel_logs` in `app/core/tracing.py` that pushes each event directly through the OTel SDK's global `LoggerProvider`. Stdout JSON output is unchanged.
- `app/main.py`: dropped `starlette_prometheus`, `PrometheusMiddleware`, and the `/metrics` route.
- `pyproject.toml`: removed `prometheus-client` and `starlette-prometheus`.

**Compose changes:**
- Dropped: `prometheus`, `loki`, `promtail`, `tempo`, `grafana` services (5 removed).
- Approach shift: instead of authoring custom SigNoz config files (`signoz/clickhouse-config.xml`, `signoz/otel-collector-config.yml`), the implementation vendors SigNoz's upstream `deploy/` tree under `deploy/` in this repo and pulls it in via Docker Compose `include:`. This avoids config drift from SigNoz's reference setup and gets schema bootstrap (`signoz-telemetrystore-migrator`) for free.

**Post-v0.113 architecture note:** SigNoz v0.113.0 (released 2026-02-25) deprecated the separate `signoz-schema-migrator` image and merged `query-service` + `frontend` into a single unified `signoz/signoz` binary on port 8080 (not 3301 as originally designed). The implementation uses the post-v0.113 architecture. The design doc's `localhost:3301` reference is incorrect; SigNoz UI is at `localhost:8080`.

Implemented across 22 tasks (commits 2026-05-13 to 2026-05-14). Key commits: `bc11324` (vendor SigNoz upstream compose, drop Grafana stack), `ef379b4` (point app at external SigNoz stack via signoz-net), `0f4a607` (update README/ARCHITECTURE/SPEC for SigNoz).

## Consequences

**Easier:**
- One UI (`localhost:8080`) for traces, metrics, and logs.
- Service map, RED metrics, exception tracker, and log explorer are auto-built by SigNoz APM defaults.
- No Docker log driver fragility (no Promtail, no file-mount workarounds).
- Single `deploy/` config directory instead of four.
- No `/metrics` scrape endpoint to maintain or document.

**Harder / constrained:**
- SigNoz Community Edition has no built-in auth. Same posture as the prior Grafana anonymous-viewer setup. Add a reverse proxy if auth is needed.
- ClickHouse cold start takes ~30s. `docker compose up` must wait for ClickHouse health before the collector and signoz binary start.
- SigNoz's dashboard authoring is less expressive than Grafana's. The 3 custom Grafana dashboards (TNA Overview, TNA Logs, TNA Extraction) were dropped; SigNoz defaults cover the main use cases. Custom dashboards can be re-added later.
- Higher RAM floor: ~1.5 GB for ClickHouse vs ~500 MB for the full Grafana stack.
- OTel Python Logs SDK is in `opentelemetry.sdk._logs` (underscore prefix, provisional). Pin a version range in `pyproject.toml`.

**What we gave up:**
- 3 custom Grafana dashboards (historical; the JSON is in `docs/superpowers/` if needed).
- The `docker-compose.override.yml.example` (Loki Docker driver workaround) — no longer needed.
- Prometheus scrape endpoint (`/metrics` → 404).

## Alternatives considered

- **Keep Grafana stack, add SigNoz as a second platform.** Rejected: doubles the operational surface.
- **Managed observability (Datadog, Grafana Cloud).** Rejected: self-hosted Community Edition matches the current self-hosted posture; no vendor lock-in; no cost at this stage.
- **Author custom SigNoz config files** (original design intent). Rejected mid-implementation: vendoring the upstream `deploy/` tree is simpler and tracks SigNoz releases with less maintenance.
- **OTel `LoggingHandler` on stdlib root logger** (original design). Failed in practice: structlog's `PrintLoggerFactory` bypasses stdlib. The custom `emit_to_otel_logs` structlog processor is the correct solution.
