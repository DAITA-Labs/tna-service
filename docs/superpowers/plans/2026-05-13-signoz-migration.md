# SigNoz Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Grafana stack (Prometheus + Loki + Promtail + Tempo + Grafana) with SigNoz Community Edition. App emits traces + metrics + logs over OTLP gRPC to a single OTel Collector that fans out to ClickHouse. One UI at `localhost:3301`. Spec: `docs/superpowers/specs/2026-05-13-signoz-migration-design.md`.

**Architecture:** Single OTLP gRPC pipe from the app carries all three signals. OTel Collector exports to ClickHouse (one storage). SigNoz query-service + frontend render the UI. `prometheus_client` is dropped in favour of the OTel Metrics SDK; structlog continues to emit JSON events, and an OTel `LoggingHandler` bridges them to OTLP.

**Tech Stack:** OpenTelemetry SDK (traces + metrics + logs), SigNoz Community Edition (signoz/query-service, signoz/frontend, signoz/signoz-otel-collector), ClickHouse 24.x, Docker Compose, FastAPI, structlog.

**Conventions:**
- Tests use `.venv/Scripts/python.exe -m pytest tests -q -m "not live"` (Windows venv).
- Commit at the end of every task.
- No task/plan refs in code comments.

---

## File structure

**Modified (existing):**
- `app/core/tracing.py` — extend `configure_tracing()` to set up MeterProvider + LoggerProvider alongside the existing TracerProvider; return the LoggerProvider so `main.py` can wire the stdlib handler
- `app/core/logs.py` — add `attach_otel_log_handler(logger_provider)` helper
- `app/core/telemetry.py` — full rewrite, prometheus_client → OTel Metrics SDK
- `app/main.py` — call `attach_otel_log_handler` after `configure_tracing`; remove `starlette_prometheus` middleware and `/metrics` route
- `app/services/extraction.py` — update metric call sites
- `app/services/agents/_base.py` — update metric call sites
- `app/services/llm_provider.py` — update metric call sites
- `app/repositories/workbook_tools/_registry.py` — update metric call sites
- `tests/unit/test_telemetry_additions.py` — adapt collector-existence tests to OTel API
- `pyproject.toml` — drop `prometheus-client` and `starlette-prometheus`
- `docker-compose.yml` — swap 5 services out, 4 services in; update api env
- `README.md`, `ARCHITECTURE.md`, `docs/SPEC.md` — describe SigNoz only
- `docs/superpowers/specs/2026-05-13-signoz-migration-design.md` — flip Status to Implemented at end

**Created:**
- `signoz/clickhouse-config.xml`
- `signoz/otel-collector-config.yml`

**Deleted:**
- `prometheus/` directory and its `prometheus.yml`
- `loki/` directory and `loki-config.yml`
- `promtail/` directory and `promtail-config.yml`
- `tempo/` directory and `tempo.yml`
- `grafana/` directory and all its dashboards/datasources/configs
- `docker-compose.override.yml.example` (Loki Docker driver workaround)

---

## Phase 1 — Application code migration

### Task 1: Extend `configure_tracing()` with MeterProvider + LoggerProvider

**Files:**
- Modify: `app/core/tracing.py`

- [ ] **Step 1: Read the existing `tracing.py`**

Inspect the current `configure_tracing()` to understand what's already there (TracerProvider + OTLPSpanExporter + propagators + httpx instrumentation).

- [ ] **Step 2: Extend `configure_tracing()` to also set up metrics + logs providers**

Modify `configure_tracing()` so it ALSO initialises a MeterProvider and a LoggerProvider, both pointing at the same OTLP endpoint. Return the LoggerProvider so `main.py` can attach the stdlib handler.

```python
# app/core/tracing.py
"""OpenTelemetry initialisation: traces, metrics, logs over OTLP gRPC.

All three signal streams use the same OTLP endpoint (defaulted from the
OTEL_EXPORTER_OTLP_ENDPOINT env var). Idempotent — repeated calls do nothing.

Usage at app startup:
    logger_provider = configure_tracing(service_name="tna-service")
    from app.core.logs import attach_otel_log_handler
    attach_otel_log_handler(logger_provider)
"""
from __future__ import annotations
import os


# Lazy imports inside functions so the module is importable when the OTel SDK
# isn't installed (local dev outside containers).


def configure_tracing(service_name: str = "tna-service",
                     otlp_endpoint: str | None = None):
    """Set up TracerProvider + MeterProvider + LoggerProvider with OTLP export.

    Returns the LoggerProvider for the caller to attach a stdlib handler.
    Returns None if OTel packages aren't available.
    """
    try:
        from opentelemetry import trace, metrics, _logs
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    except ImportError:
        return None

    # Idempotent: only initialise once.
    if trace.get_tracer_provider().__class__.__name__ != "ProxyTracerProvider":
        # Already configured — caller can still get the existing LoggerProvider.
        return _logs.get_logger_provider()

    endpoint = (otlp_endpoint
                or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
                or os.environ.get("TEMPO_OTLP_ENDPOINT")  # back-compat
                or "http://otel-collector:4317")
    resource = Resource.create({"service.name": service_name})

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=endpoint, insecure=True)
    ))
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=15_000,
    )
    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    ))

    # Logs
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(
        OTLPLogExporter(endpoint=endpoint, insecure=True)
    ))
    _logs.set_logger_provider(logger_provider)

    # Propagators (existing — keep)
    try:
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
        from opentelemetry.propagators.b3 import B3MultiFormat
        set_global_textmap(CompositePropagator([
            TraceContextTextMapPropagator(),
            B3MultiFormat(),
        ]))
    except ImportError:
        pass

    # Instrument httpx for outgoing trace context propagation (existing — keep)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except ImportError:
        pass

    return logger_provider
```

Preserve the existing `get_tracer()` and `add_trace_context_to_log()` functions at the bottom of the file unchanged.

- [ ] **Step 3: Run tests to confirm tracing.py still imports cleanly**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live" -x --timeout=60
```
Expected: 209 passed (no behaviour change — OTel SDK isn't installed locally; the lazy imports return None gracefully).

- [ ] **Step 4: Commit**

```bash
git add app/core/tracing.py
git commit -m "feat(telemetry): extend configure_tracing with MeterProvider + LoggerProvider for OTLP push"
```

---

### Task 2: Add `attach_otel_log_handler()` in `logs.py`

**Files:**
- Modify: `app/core/logs.py`

- [ ] **Step 1: Read the existing `logs.py`**

Confirm it has `configure_logging()` + imports `add_trace_context_to_log` from `app.core.tracing`.

- [ ] **Step 2: Add the helper function**

Append to `app/core/logs.py`:

```python
def attach_otel_log_handler(logger_provider) -> None:
    """Attach an OTel LoggingHandler to the stdlib root logger.

    structlog routes through `logging.getLogger(name)`, so any handler on the
    root logger receives every event. The OTel handler converts each LogRecord
    into an OTel-format record and ships it via OTLP. trace_id and span_id
    from the current span are attached automatically by the OTel SDK.

    No-op when the OTel SDK isn't installed (logger_provider is None).
    """
    if logger_provider is None:
        return
    try:
        import logging
        from opentelemetry.sdk._logs import LoggingHandler
        handler = LoggingHandler(level=logging.INFO,
                                 logger_provider=logger_provider)
        logging.getLogger().addHandler(handler)
    except ImportError:
        pass
```

- [ ] **Step 3: Verify import doesn't break tests**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live" -x --timeout=60
```
Expected: 209 passed.

- [ ] **Step 4: Commit**

```bash
git add app/core/logs.py
git commit -m "feat(telemetry): attach_otel_log_handler bridges stdlib logging -> OTLP"
```

---

### Task 3: Wire the log handler in `main.py`

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Read current `main.py`**

Note that `configure_tracing(...)` is currently called without using its return value, and that `PrometheusMiddleware` + `/metrics` route are still present.

- [ ] **Step 2: Capture LoggerProvider + attach OTel log handler**

Edit `app/main.py`. Replace the tracing-init block with a version that captures the LoggerProvider and attaches the log handler:

```python
"""FastAPI app entry point — wires routers + telemetry + structured logging."""
import os
from fastapi import FastAPI
from app.config.settings import get_settings
from app.core.logs import configure_logging, attach_otel_log_handler
from app.core.middleware import RequestIdMiddleware
from app.core.telemetry import extractions_total  # noqa: F401 — register collectors
from app.routers.extract import router as extract_router
from app.routers.health import router as health_router
from app.enums.environment import Environment


_settings = get_settings()
_in_container = os.path.exists("/.dockerenv") or os.environ.get("LOG_FORMAT") == "json"
configure_logging(
    level=_settings.log_level,
    json_output=_in_container or _settings.app_env != Environment.DEVELOPMENT,
)

# OTel for traces + metrics + logs. Initialise inside containers (the OTel SDK
# is installed there), or when explicitly opted in via OTEL_ENABLED.
_tracing_enabled = _in_container or os.environ.get("OTEL_ENABLED", "").lower() in ("1", "true", "yes")
_logger_provider = None
if _tracing_enabled:
    try:
        from app.core.tracing import configure_tracing
        _logger_provider = configure_tracing(service_name="tna-service")
        attach_otel_log_handler(_logger_provider)
    except ImportError:
        _tracing_enabled = False


app = FastAPI(title="TNA Service", version="0.1.0")

if _tracing_enabled:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        pass

app.add_middleware(RequestIdMiddleware)
app.include_router(extract_router)
app.include_router(health_router)
```

Notes:
- Removed `from starlette_prometheus import metrics, PrometheusMiddleware`
- Removed `app.add_middleware(PrometheusMiddleware)`
- Removed `app.add_route("/metrics", metrics)`
- Removed the `extraction_duration_seconds` noqa import (we'll replace with a current OTel-era collector name in Task 5)

- [ ] **Step 3: Run tests**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live" -x --timeout=60
```

Expected: 209 passed. If `app.core.telemetry` import fails because `extractions_total` doesn't exist yet, that's OK — we replace this name when we rewrite `telemetry.py`. For now use a name we know exists. If you need to keep imports valid, change the import to `from app.core.telemetry import *` for one task (cleaned up in Task 5).

If the test interface tests (`tests/unit/test_interface.py`, `tests/unit/test_middleware.py`) fail because of `starlette_prometheus`, that's expected and resolved when we remove the dep in Task 10. Skip those if needed:

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live" -x --timeout=60 \
  --ignore=tests/unit/test_interface.py --ignore=tests/unit/test_middleware.py
```

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat(telemetry): wire OTel log handler in main; drop Prometheus middleware + /metrics route"
```

---

### Task 4: Rewrite `app/core/telemetry.py` to use OTel Metrics SDK

**Files:**
- Modify: `app/core/telemetry.py`

- [ ] **Step 1: Read the current `telemetry.py`**

Catalogue all collectors and their labels. We need to recreate every one in the OTel API with the same name and same labels (now attributes).

- [ ] **Step 2: Replace contents wholesale**

Full file replacement:

```python
"""Prometheus-style telemetry collectors, implemented on the OTel Metrics SDK.

Every collector name and label set is preserved from the prometheus_client
era. Labels are passed at call time as the `attributes` dict, e.g.:

    extractions_total.add(1, {"status": "success"})
    agent_duration_seconds.record(0.45, {"agent": "field_namer", "status": "success"})

The OTel MeterProvider is initialised in app/core/tracing.py and exports to
the configured OTLP endpoint every 15s.
"""
from __future__ import annotations


# Lazy meter accessor — works even when OTel SDK isn't installed (returns
# noop instruments so .add()/.record() are silent no-ops).
def _meter():
    try:
        from opentelemetry import metrics
        return metrics.get_meter(__name__)
    except ImportError:
        return _NoopMeter()


class _NoopInstrument:
    def add(self, *_args, **_kwargs): pass
    def record(self, *_args, **_kwargs): pass


class _NoopMeter:
    def create_counter(self, *_args, **_kwargs): return _NoopInstrument()
    def create_histogram(self, *_args, **_kwargs): return _NoopInstrument()
    def create_up_down_counter(self, *_args, **_kwargs): return _NoopInstrument()
    def create_observable_gauge(self, *_args, **_kwargs): return _NoopInstrument()


_m = _meter()


# Extractions ----------------------------------------------------------------

extractions_total = _m.create_counter(
    "extractions_total",
    description="Total invocations of the extract() orchestrator.",
)

extraction_duration_seconds = _m.create_histogram(
    "extraction_duration_seconds",
    description="End-to-end extract() duration.",
    unit="s",
)

extraction_pli_count = _m.create_up_down_counter(
    "extraction_pli_count",
    description="PLI count emitted per file (set per-extraction).",
)

plis_extracted_total = _m.create_counter(
    "plis_extracted_total",
    description="Cumulative PLI rows emitted across all extractions.",
)

extraction_phase_duration_seconds = _m.create_histogram(
    "extraction_phase_duration_seconds",
    description="Per-phase latency within a single extraction request.",
    unit="s",
)


# Agents ---------------------------------------------------------------------

agent_calls_total = _m.create_counter(
    "agent_calls_total",
    description="Total agent invocations.",
)

agent_duration_seconds = _m.create_histogram(
    "agent_duration_seconds",
    description="Per-agent run duration.",
    unit="s",
)

agent_retry_count = _m.create_counter(
    "agent_retry_count",
    description="Per-agent retry occurrences.",
)

agent_tokens_input = _m.create_counter(
    "agent_tokens_input",
    description="Cumulative input tokens consumed by agents.",
)

agent_tokens_output = _m.create_counter(
    "agent_tokens_output",
    description="Cumulative output tokens produced by LLM responses.",
)


# LLM provider ---------------------------------------------------------------

llm_calls_total = _m.create_counter(
    "llm_calls_total",
    description="Total LLM API invocations.",
)

llm_inference_duration_seconds = _m.create_histogram(
    "llm_inference_duration_seconds",
    description="Per-LLM-call duration.",
    unit="s",
)


# Tools ----------------------------------------------------------------------

tool_calls_total = _m.create_counter(
    "tool_calls_total",
    description="Total @tool-registered workbook tool invocations.",
)

tool_duration_seconds = _m.create_histogram(
    "tool_duration_seconds",
    description="Per-tool latency.",
    unit="s",
)

tool_errors_total = _m.create_counter(
    "tool_errors_total",
    description="Per-tool error count.",
)


# Validators -----------------------------------------------------------------

validator_findings_total = _m.create_counter(
    "validator_findings_total",
    description="Validation findings emitted, by check + severity.",
)
```

Note: this is a `validator_findings_total` — the prior version was called `validator_findings`. Keep the original name to avoid breaking dashboards / consumers; rename in `telemetry.py` to match what verifiers call: check `app/services/validation/source_cell_verifier.py` for the existing name and align both sides.

- [ ] **Step 3: Make sure call-site names still resolve**

```
.venv/Scripts/python.exe -c "from app.core.telemetry import extractions_total, agent_calls_total, tool_calls_total, llm_calls_total, agent_duration_seconds, agent_retry_count, agent_tokens_input, agent_tokens_output, validator_findings_total, extraction_pli_count, plis_extracted_total, extraction_phase_duration_seconds, tool_duration_seconds, tool_errors_total, extraction_duration_seconds, llm_inference_duration_seconds; print('all imports ok')"
```

Expected: `all imports ok`.

- [ ] **Step 4: Run tests (will partially fail; that's expected)**

```
.venv/Scripts/python.exe -m pytest tests/unit/test_telemetry.py tests/unit/test_telemetry_additions.py -q
```

Expected: telemetry tests will fail because they assert on `._labelnames` (prometheus_client private API). We fix in Task 11.

For the full suite excluding the telemetry tests:
```
.venv/Scripts/python.exe -m pytest tests -q -m "not live" \
  --ignore=tests/unit/test_telemetry.py \
  --ignore=tests/unit/test_telemetry_additions.py \
  --ignore=tests/unit/test_interface.py \
  --ignore=tests/unit/test_middleware.py
```

Expected: ~200 passed (minus the four ignored files).

- [ ] **Step 5: Commit**

```bash
git add app/core/telemetry.py
git commit -m "feat(telemetry): rewrite collectors using OTel Metrics SDK (drop prometheus_client API)"
```

---

### Task 5: Update call sites in `app/services/extraction.py`

**Files:**
- Modify: `app/services/extraction.py`

The OTel API uses `.add(1, attrs)` and `.record(value, attrs)` instead of `.labels(...).inc()` and `.labels(...).observe(value)`.

- [ ] **Step 1: Find and update all metric call sites**

Grep for them first:
```
grep -n "extractions_total\|extraction_duration_seconds\|extraction_pli_count\|plis_extracted_total\|extraction_phase_duration_seconds" app/services/extraction.py
```

Replace each one with the OTel API. Examples:

```python
# was:
extractions_total.labels(status="success").inc()
# now:
extractions_total.add(1, {"status": "success"})

# was:
extraction_duration_seconds.labels(format_detected=fmt).observe(elapsed)
# now:
extraction_duration_seconds.record(elapsed, {"format_detected": fmt or "unknown"})

# was:
extraction_pli_count.labels(source_file=name).set(len(plis))
# now (UpDownCounter has no .set; use .add with the delta — or compute delta and add)
# For per-file gauges where you want to overwrite: simplest is to skip setting it
# (it's a per-file value, not a cumulative — the dashboard reads point-in-time).
# OR: just .add() the delta if you track prior value.
# RECOMMENDED: replace this metric with extractions_total + plis_extracted_total
# in the dashboard. For now, swap to: extraction_pli_count.add(len(plis), {"source_file": name})
extraction_pli_count.add(len(plis), {"source_file": ctx.path.name})

# was:
plis_extracted_total.inc(len(final.plis))
# now:
plis_extracted_total.add(len(final.plis))

# was:
extraction_phase_duration_seconds.labels(phase=name).observe(elapsed)
# now:
extraction_phase_duration_seconds.record(elapsed, {"phase": name})
```

Read the file, find every occurrence of `.labels(`, `.inc(`, `.observe(`, `.set(`, and rewrite them to the OTel API.

- [ ] **Step 2: Verify imports still work**

```
.venv/Scripts/python.exe -c "import app.services.extraction; print('import ok')"
```

- [ ] **Step 3: Run the test suite (still partially broken)**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live" \
  --ignore=tests/unit/test_telemetry.py \
  --ignore=tests/unit/test_telemetry_additions.py \
  --ignore=tests/unit/test_interface.py \
  --ignore=tests/unit/test_middleware.py
```

Expected: ~200 passed.

- [ ] **Step 4: Commit**

```bash
git add app/services/extraction.py
git commit -m "feat(telemetry): port extraction.py metric call sites to OTel API"
```

---

### Task 6: Update call sites in `app/services/agents/_base.py`

**Files:**
- Modify: `app/services/agents/_base.py`

- [ ] **Step 1: Find current metric usage**

```
grep -n "agent_calls_total\|agent_duration_seconds\|agent_retry_count" app/services/agents/_base.py
```

- [ ] **Step 2: Rewrite each call site**

```python
# was:
agent_duration_seconds.labels(agent=name, status="success").observe(elapsed)
# now:
agent_duration_seconds.record(elapsed, {"agent": name, "status": "success"})

# was:
agent_calls_total.labels(agent=name, status="success").inc()
# now:
agent_calls_total.add(1, {"agent": name, "status": "success"})

# was:
agent_retry_count.labels(agent=name, reason="schema_validation").inc()
# now:
agent_retry_count.add(1, {"agent": name, "reason": "schema_validation"})
```

- [ ] **Step 3: Run tests**

```
.venv/Scripts/python.exe -m pytest tests/agent -q
```
Expected: agent tests still pass (they don't depend on prometheus_client APIs).

- [ ] **Step 4: Commit**

```bash
git add app/services/agents/_base.py
git commit -m "feat(telemetry): port agents/_base.py metric call sites to OTel API"
```

---

### Task 7: Update call sites in `app/services/llm_provider.py`

**Files:**
- Modify: `app/services/llm_provider.py`

- [ ] **Step 1: Find metric calls**

```
grep -n "llm_calls_total\|llm_inference_duration_seconds\|agent_tokens_input\|agent_tokens_output" app/services/llm_provider.py
```

- [ ] **Step 2: Rewrite each call site**

```python
# was:
llm_inference_duration_seconds.labels(model=self.model).observe(elapsed)
# now:
llm_inference_duration_seconds.record(elapsed, {"model": self.model})

# was:
llm_calls_total.labels(model=self.model, status="success").inc()
# now:
llm_calls_total.add(1, {"model": self.model, "status": "success"})

# was:
agent_tokens_input.labels(agent=agent_name, model=self.model).inc(input_tokens)
# now:
agent_tokens_input.add(input_tokens, {"agent": agent_name, "model": self.model})

# was:
agent_tokens_output.labels(agent=agent_name, model=self.model).inc(output_tokens)
# now:
agent_tokens_output.add(output_tokens, {"agent": agent_name, "model": self.model})
```

- [ ] **Step 3: Run tests**

```
.venv/Scripts/python.exe -m pytest tests/unit/test_llm_provider.py -q
```
Expected: passes if the test doesn't depend on prometheus_client internals.

- [ ] **Step 4: Commit**

```bash
git add app/services/llm_provider.py
git commit -m "feat(telemetry): port llm_provider.py metric call sites to OTel API"
```

---

### Task 8: Update call sites in `app/repositories/workbook_tools/_registry.py`

**Files:**
- Modify: `app/repositories/workbook_tools/_registry.py`

- [ ] **Step 1: Find metric calls**

```
grep -n "tool_calls_total\|tool_duration_seconds\|tool_errors_total" app/repositories/workbook_tools/_registry.py
```

- [ ] **Step 2: Rewrite each call site**

```python
# was:
tool_calls_total.labels(tool_name=name).inc()
# now:
tool_calls_total.add(1, {"tool_name": name})

# was:
tool_duration_seconds.labels(tool_name=name).observe(elapsed)
# now:
tool_duration_seconds.record(elapsed, {"tool_name": name})

# was:
tool_errors_total.labels(tool_name=name).inc()
# now:
tool_errors_total.add(1, {"tool_name": name})
```

- [ ] **Step 3: Run repository tests**

```
.venv/Scripts/python.exe -m pytest tests/unit/repositories -q
```
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add app/repositories/workbook_tools/_registry.py
git commit -m "feat(telemetry): port tool registry metric call sites to OTel API"
```

---

### Task 9: Update call sites in the 4 extraction validators

**Files:**
- Modify: `app/services/validation/source_cell_verifier.py`
- Modify: `app/services/validation/header_match_verifier.py`
- Modify: `app/services/validation/coverage_verifier.py`
- Modify: `app/services/validation/field_dropout_verifier.py`

- [ ] **Step 1: Find metric calls in each**

```
grep -n "validator_findings" app/services/validation/*.py
```

The historical name in `prometheus_client` was `validator_findings` with `.labels(check=..., severity=...).inc()`. In the new OTel SDK we use `validator_findings_total` with `.add(1, {...})`.

- [ ] **Step 2: Rewrite each call site in each file**

```python
# was:
validator_findings.labels(check="source_cell", severity="warn").inc()
# now:
validator_findings_total.add(1, {"check": "source_cell", "severity": "warn"})
```

Update the import at the top of each file:
```python
# was:
from app.core.telemetry import validator_findings
# now:
from app.core.telemetry import validator_findings_total
```

- [ ] **Step 3: Run validator tests**

```
.venv/Scripts/python.exe -m pytest tests/unit/validation -q
```
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add app/services/validation/
git commit -m "feat(telemetry): port validator metric call sites to OTel API"
```

---

### Task 10: Drop `prometheus_client` + `starlette_prometheus` from `pyproject.toml`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Remove the two deps**

Find and remove from the `[project] dependencies` list:
```
"prometheus-client>=0.20.0",
"starlette-prometheus>=0.10.0",
```

- [ ] **Step 2: Confirm no remaining imports**

```
grep -rn "prometheus_client\|starlette_prometheus" app/ tests/
```

Expected: zero matches in `app/` or `tests/`. If there are stragglers, fix them.

- [ ] **Step 3: Run the FULL test suite**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```

Expected: previously-failing tests (test_interface, test_middleware) now resolve their import issues. Test count should land near 209.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: drop prometheus_client + starlette_prometheus deps"
```

---

### Task 11: Update telemetry-existence tests to OTel API

**Files:**
- Modify: `tests/unit/test_telemetry_additions.py`
- Modify: `tests/unit/test_telemetry.py` (if it uses prometheus_client internals)

- [ ] **Step 1: Read current test contents**

The historical tests check things like `agent_calls_total._labelnames == ("agent", "status")`. That's a prometheus_client private attr; OTel instruments don't expose label names that way.

- [ ] **Step 2: Rewrite assertions**

Update each test to check what we CAN verify on an OTel instrument:
- That the import succeeds (instrument exists)
- That `.add()` / `.record()` doesn't raise

```python
# tests/unit/test_telemetry_additions.py
"""Smoke tests that the OTel-era collectors exist and are callable."""
from app.core.telemetry import (
    extractions_total, agent_calls_total, llm_calls_total,
    tool_calls_total, tool_duration_seconds, tool_errors_total,
    agent_tokens_input, agent_tokens_output, plis_extracted_total,
    extraction_phase_duration_seconds, agent_duration_seconds,
)


def test_extractions_total_is_callable():
    extractions_total.add(1, {"status": "success"})  # must not raise


def test_agent_calls_total_is_callable():
    agent_calls_total.add(1, {"agent": "test", "status": "success"})


def test_llm_calls_total_is_callable():
    llm_calls_total.add(1, {"model": "test-model", "status": "success"})


def test_tool_call_increments_counter(tmp_path):
    from app.repositories.workbook_tools._registry import TOOL_REGISTRY
    import app.repositories.workbook_tools.survey  # noqa: F401 — register
    from app.repositories.workbook_repo import register_workbook, clear_cache
    from openpyxl import Workbook
    clear_cache()
    wb = Workbook(); wb.active["A1"] = "x"
    p = tmp_path / "x.xlsx"; wb.save(p)
    ctx = register_workbook(p)
    # tool_calls_total is now OTel — we can't read its value, just verify it doesn't raise
    TOOL_REGISTRY.get("list_sheets")(ctx)


def test_tool_errors_total_is_callable():
    tool_errors_total.add(1, {"tool_name": "x"})


def test_plis_extracted_total_is_callable():
    plis_extracted_total.add(7)


def test_extraction_phase_duration_is_callable():
    extraction_phase_duration_seconds.record(0.1, {"phase": "test"})


def test_agent_duration_is_callable():
    agent_duration_seconds.record(0.1, {"agent": "test", "status": "success"})
```

- [ ] **Step 3: Update `tests/unit/test_telemetry.py` similarly**

Read its contents; any prometheus_client-specific assertions get the same treatment. Drop label-name checks; keep callability checks.

- [ ] **Step 4: Run the full suite**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```
Expected: 209 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_telemetry_additions.py tests/unit/test_telemetry.py
git commit -m "test(telemetry): port collector-existence tests to OTel API"
```

---

### Task 12: Verify Phase 1 complete

- [ ] **Step 1: Full suite green**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```
Expected: 209 passed.

- [ ] **Step 2: No prometheus_client references in app/ or tests/**

```
grep -rn "prometheus_client\|starlette_prometheus\|/metrics" app/ tests/
```
Expected: zero matches (or only matches in `tests/` that are intentionally testing the absence — none currently).

- [ ] **Step 3: No commit (verification only)**

---

## Phase 2 — Compose swap

### Task 13: Create `signoz/clickhouse-config.xml`

**Files:**
- Create: `signoz/clickhouse-config.xml`

- [ ] **Step 1: Write the config**

```xml
<?xml version="1.0"?>
<!-- Minimal single-node ClickHouse config for SigNoz storage. -->
<clickhouse>
  <logger>
    <level>information</level>
    <console>1</console>
  </logger>
  <listen_host>0.0.0.0</listen_host>
  <http_port>8123</http_port>
  <tcp_port>9000</tcp_port>

  <path>/var/lib/clickhouse/</path>
  <tmp_path>/var/lib/clickhouse/tmp/</tmp_path>
  <user_files_path>/var/lib/clickhouse/user_files/</user_files_path>

  <max_connections>4096</max_connections>
  <keep_alive_timeout>3</keep_alive_timeout>
  <max_concurrent_queries>100</max_concurrent_queries>
  <uncompressed_cache_size>8589934592</uncompressed_cache_size>
  <mark_cache_size>5368709120</mark_cache_size>
  <mlock_executable>true</mlock_executable>

  <users>
    <default>
      <password></password>
      <networks><ip>::/0</ip></networks>
      <profile>default</profile>
      <quota>default</quota>
      <access_management>1</access_management>
    </default>
  </users>
</clickhouse>
```

- [ ] **Step 2: Validate as XML**

```
.venv/Scripts/python.exe -c "import xml.etree.ElementTree as ET; ET.parse('signoz/clickhouse-config.xml'); print('valid XML')"
```

- [ ] **Step 3: Commit**

```bash
git add signoz/clickhouse-config.xml
git commit -m "feat(observability): ClickHouse config for SigNoz storage"
```

---

### Task 14: Create `signoz/otel-collector-config.yml`

**Files:**
- Create: `signoz/otel-collector-config.yml`

- [ ] **Step 1: Write the config**

```yaml
# OTel Collector config for SigNoz pipeline.
# Receives OTLP gRPC + HTTP from the api; exports to ClickHouse via three exporters.

receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
  resourcedetection:
    detectors: [env, system]
  memory_limiter:
    check_interval: 1s
    limit_mib: 1500
    spike_limit_mib: 512

exporters:
  clickhousetraces:
    datasource: tcp://clickhouse:9000
  clickhousemetricswrite:
    endpoint: tcp://clickhouse:9000
  clickhouselogsexporter:
    dsn: tcp://clickhouse:9000

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, resourcedetection, batch]
      exporters: [clickhousetraces]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, resourcedetection, batch]
      exporters: [clickhousemetricswrite]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, resourcedetection, batch]
      exporters: [clickhouselogsexporter]
```

- [ ] **Step 2: Validate as YAML**

```
.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('signoz/otel-collector-config.yml')); print('valid YAML')"
```

- [ ] **Step 3: Commit**

```bash
git add signoz/otel-collector-config.yml
git commit -m "feat(observability): OTel Collector config (3 pipelines -> ClickHouse)"
```

---

### Task 15: Swap docker-compose.yml services

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Read current `docker-compose.yml`**

Note the existing services: api, prometheus, loki, promtail, tempo, grafana.

- [ ] **Step 2: Replace with the new compose definition**

Write the new compose contents:

```yaml
services:
  api:
    build:
      context: .
    image: tna-service:dev
    container_name: tna-service-api
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - APP_ENV=${APP_ENV:-production}
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
      - OTEL_SERVICE_NAME=tna-service
    volumes:
      - ./dataset:/app/dataset:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      - otel-collector
    networks: [observability]

  clickhouse:
    image: clickhouse/clickhouse-server:24.1.2-alpine
    container_name: tna-service-clickhouse
    volumes:
      - clickhouse-data:/var/lib/clickhouse
      - ./signoz/clickhouse-config.xml:/etc/clickhouse-server/config.d/local.xml:ro
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "localhost:8123/ping"]
      interval: 30s
      timeout: 5s
      retries: 3
    networks: [observability]

  otel-collector:
    image: signoz/signoz-otel-collector:0.111.7
    container_name: tna-service-otel-collector
    command: ["--config=/etc/otelcol/config.yml"]
    volumes:
      - ./signoz/otel-collector-config.yml:/etc/otelcol/config.yml:ro
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
    depends_on:
      clickhouse: { condition: service_healthy }
    networks: [observability]

  signoz-query-service:
    image: signoz/query-service:0.55.0
    container_name: tna-service-signoz-query
    environment:
      - ClickHouseUrl=tcp://clickhouse:9000
      - STORAGE=clickhouse
      - SIGNOZ_LOCAL_DB_PATH=/var/lib/signoz/signoz.db
    volumes:
      - signoz-data:/var/lib/signoz
    depends_on:
      clickhouse: { condition: service_healthy }
    networks: [observability]

  signoz-frontend:
    image: signoz/frontend:0.55.0
    container_name: tna-service-signoz-frontend
    ports:
      - "3301:3301"
    environment:
      - FRONTEND_API_ENDPOINT=http://signoz-query-service:8080
    depends_on:
      - signoz-query-service
    networks: [observability]

networks:
  observability: {}

volumes:
  clickhouse-data: {}
  signoz-data: {}
```

- [ ] **Step 3: Validate**

```
.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('docker-compose.yml')); print('valid YAML')"
docker compose config > /dev/null && echo "compose config valid"
```

- [ ] **Step 4: Bring the new stack up**

```
docker compose down -v   # tear down old stack (this WILL remove old volumes — Prom/Loki/Tempo data gone)
docker compose up -d --build
sleep 60  # ClickHouse takes ~30s to initialise
docker compose ps
```

Expected: 5 containers, ClickHouse "healthy".

- [ ] **Step 5: Verify SigNoz UI loads**

In a browser, open `http://localhost:3301`. You should see the SigNoz dashboard. It'll be empty since no extracts have run yet.

- [ ] **Step 6: Trigger an extract**

```
curl -F "file=@dataset/CHRISTIAN BERG- T&A.xlsx" http://localhost:8000/extract -o /dev/null -s -w "%{http_code}\n"
```

Expected: 200. Wait 30s, then refresh SigNoz UI. The Services tab should show `tna-service`.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(observability): swap compose to SigNoz stack (clickhouse + otel-collector + signoz-query + signoz-frontend)"
```

---

### Task 16: Verify Phase 2 complete

- [ ] **Step 1: Services running**

```
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```
Expected: api, clickhouse, otel-collector, signoz-query-service, signoz-frontend — all up.

- [ ] **Step 2: Traces flowing**

```
curl -F "file=@dataset/CHRISTIAN BERG- T&A.xlsx" -H "x-request-id: phase2-verify-$(date +%s)" http://localhost:8000/extract -o /dev/null -s -w "%{http_code}\n"
sleep 30
docker exec tna-service-clickhouse clickhouse-client -q "SELECT count(*) FROM signoz_traces.signoz_index_v2"
```
Expected: non-zero trace count.

- [ ] **Step 3: Metrics flowing**

```
docker exec tna-service-clickhouse clickhouse-client -q "SELECT count(DISTINCT metric_name) FROM signoz_metrics.distributed_time_series_v4"
```
Expected: non-zero metric count.

- [ ] **Step 4: Logs flowing**

```
docker exec tna-service-clickhouse clickhouse-client -q "SELECT count(*) FROM signoz_logs.distributed_logs"
```
Expected: non-zero log count.

- [ ] **Step 5: No commit (verification only)**

---

## Phase 3 — Cleanup + docs

### Task 17: Delete old observability config directories

**Files:**
- Delete: `prometheus/`, `loki/`, `promtail/`, `tempo/`, `grafana/`
- Delete: `docker-compose.override.yml.example`

- [ ] **Step 1: Confirm directories exist**

```
ls -la prometheus loki promtail tempo grafana docker-compose.override.yml.example 2>&1
```

- [ ] **Step 2: Remove with git**

```
git rm -r prometheus loki promtail tempo grafana
git rm docker-compose.override.yml.example
```

- [ ] **Step 3: Verify**

```
ls prometheus loki promtail tempo grafana 2>&1
```
Expected: "No such file or directory" for each.

- [ ] **Step 4: Run tests**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```
Expected: 209 passed.

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: remove Grafana stack config dirs (prometheus, loki, promtail, tempo, grafana)"
```

---

### Task 18: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README sections about observability**

Look for sections `## Telemetry`, `## Logs (Loki)`, `## Make targets` (which references `make up` bringing up Prometheus + Grafana), and Quick start (which references `prom → http://localhost:9090`, `grafana → http://localhost:3000`).

- [ ] **Step 2: Replace Telemetry + Logs sections**

Replace with a single SigNoz-focused section:

```markdown
## Observability (SigNoz)

The full observability stack runs in Docker alongside the api: ClickHouse
(storage), OTel Collector (ingest), SigNoz query-service + frontend (UI).
Open `http://localhost:3301` after `make up` to see traces, metrics, and
logs in one place.

The app emits three signals over a single OTLP gRPC connection:

- **Traces** via OpenTelemetry SDK — every `/extract` request is a root
  span; per-phase/agent/LLM/tool spans nested underneath.
- **Metrics** via OpenTelemetry Metrics SDK — counters and histograms
  for extracts, agents, tools, LLM calls, token usage, phase duration.
- **Logs** via OpenTelemetry Logs SDK — structured JSON events bridged
  through stdlib logging; trace_id/span_id auto-attached.

W3C TraceContext and B3 propagation enabled — pass a `traceparent` header
to join an upstream trace; outgoing httpx calls (Anthropic SDK) propagate
trace context onward.

What you get out of the box in SigNoz:

| View | What it shows |
|---|---|
| Services | RED metrics + p50/p95 per service |
| Traces | Search by trace ID, request, attributes; full span tree |
| Logs | Filter by attribute (`agent`, `phase`, `request_id`, `trace_id`) |
| Metrics | Explorer + dashboard authoring |
| Exceptions | Auto-grouped exceptions with frequency |

Trace ID returned in the `x-request-id` response header — paste it into
SigNoz's Traces tab to view the entire extract's span tree.
```

- [ ] **Step 3: Update Quick start ports**

Find:
```
# api      → http://localhost:8000
# prom     → http://localhost:9090
# grafana  → http://localhost:3000   (anon viewer, "TNA Extraction" dashboard)
```
Replace with:
```
# api    → http://localhost:8000
# signoz → http://localhost:3301
```

- [ ] **Step 4: Update Project structure section**

Find the `tests/` block and the section above it that mentions the project layout. Remove references to `prometheus/`, `loki/`, `promtail/`, `tempo/`, `grafana/` directories. Add `signoz/` directory.

- [ ] **Step 5: Update Troubleshooting**

Remove rows referencing Loki / Promtail / Grafana / Prometheus. Add one row:

```markdown
| SigNoz UI empty after `/extract` | ClickHouse cold start takes ~30-60s on first boot | Wait, then refresh. If still empty after 2 min, `docker compose logs otel-collector` |
```

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs(readme): rewrite Telemetry + Logs sections for SigNoz; drop Grafana stack mentions"
```

---

### Task 19: Update `ARCHITECTURE.md`

**Files:**
- Modify: `ARCHITECTURE.md`

- [ ] **Step 1: Find the Telemetry section**

```
grep -n "Telemetry\|Prometheus\|Grafana\|Loki\|Tempo" ARCHITECTURE.md
```

- [ ] **Step 2: Replace it**

Rewrite the Telemetry section as:

```markdown
## Telemetry

All three observability signals flow over a single OTLP gRPC channel from
the api to an OTel Collector, which fans out to ClickHouse. SigNoz query
service + frontend render the UI at `http://localhost:3301`.

### Signal-by-signal

**Traces** — `app/core/tracing.py` initialises an OTel `TracerProvider` with
the OTLP span exporter. `FastAPIInstrumentor` auto-creates a root span per
HTTP request. The orchestrator (`app/services/extraction.py`) opens nested
spans for each phase (`phase.planner`, `phase.apply_plan`, …). `AgentRunner`
opens a span per agent invocation. `LLMProvider` opens a span around each
Anthropic call with token-count attributes. `httpx` is auto-instrumented for
outgoing trace context propagation.

**Metrics** — `app/core/telemetry.py` defines collectors via OTel Metrics SDK.
A `MeterProvider` exports via OTLP every 15s. Counters: `extractions_total`,
`plis_extracted_total`, `agent_calls_total`, `llm_calls_total`,
`tool_calls_total`, `agent_retry_count`, `agent_tokens_input`/`output`,
`tool_errors_total`, `validator_findings_total`. Histograms:
`extraction_duration_seconds`, `extraction_phase_duration_seconds`,
`agent_duration_seconds`, `tool_duration_seconds`,
`llm_inference_duration_seconds`. All carry attributes (status, agent,
model, tool_name, phase, check, severity).

**Logs** — `app/core/logs.py` configures structlog; `attach_otel_log_handler`
bridges stdlib root logger → OTel `LoggingHandler` → OTLP. Every structlog
event becomes an OTel `LogRecord` with `trace_id` + `span_id` auto-attached
from the current span context.

### Request-scoped correlation

`RequestIdMiddleware` reads or generates `x-request-id` and binds it to
structlog contextvars. The same UUID appears in the `x-request-id` response
header AND in every log line of that request. The OTel SDK independently
generates a 128-bit `trace_id` (or joins one from an incoming `traceparent`
header). Both correlate in SigNoz: log records carry both `request_id`
(business-correlation) and `trace_id` (technical-correlation).
```

- [ ] **Step 3: Drop the eval framework's Grafana mention if present**

- [ ] **Step 4: Commit**

```bash
git add ARCHITECTURE.md
git commit -m "docs(architecture): rewrite Telemetry section for SigNoz"
```

---

### Task 20: Update `docs/SPEC.md`

**Files:**
- Modify: `docs/SPEC.md`

- [ ] **Step 1: Find and update Telemetry references**

```
grep -n "Prometheus\|Grafana\|Loki\|Tempo\|Promtail" docs/SPEC.md
```

- [ ] **Step 2: Replace mentions with SigNoz**

Anywhere the spec describes telemetry, change "Prometheus/Grafana/Loki/Tempo" → "SigNoz (OTel + ClickHouse)". Note the underlying collectors are the same names — only the storage/UI changed.

- [ ] **Step 3: Commit**

```bash
git add docs/SPEC.md
git commit -m "docs(spec): replace Grafana stack mentions with SigNoz"
```

---

### Task 21: Flip design doc Status to Implemented

**Files:**
- Modify: `docs/superpowers/specs/2026-05-13-signoz-migration-design.md`

- [ ] **Step 1: Find the Status line**

```
grep -n "Status:" docs/superpowers/specs/2026-05-13-signoz-migration-design.md
```

- [ ] **Step 2: Change "Approved" → "Implemented"**

Replace:
```
**Status:** Approved, ready for implementation plan
```
With:
```
**Status:** Implemented
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-05-13-signoz-migration-design.md
git commit -m "docs: mark SigNoz migration spec as Implemented"
```

---

### Task 22: Final verification

- [ ] **Step 1: Full test suite**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```
Expected: 209 passed.

- [ ] **Step 2: Docker stack**

```
docker compose down
docker compose up -d --build
sleep 90
docker compose ps
```
Expected: 5 healthy services.

- [ ] **Step 3: Live extract through SigNoz**

```
TRACEPARENT="00-$(openssl rand -hex 16)-$(openssl rand -hex 8)-01"
curl -F "file=@dataset/CHRISTIAN BERG- T&A.xlsx" \
     -H "traceparent: $TRACEPARENT" \
     -H "x-request-id: final-verify-$(date +%s)" \
     http://localhost:8000/extract -o /dev/null -s -w "HTTP %{http_code}\n"

EXPECTED_TID=$(echo $TRACEPARENT | cut -d- -f2)
sleep 30

# Confirm the trace landed in ClickHouse with the propagated trace ID
docker exec tna-service-clickhouse clickhouse-client -q \
  "SELECT count(*) FROM signoz_traces.signoz_index_v2 WHERE traceID = '$EXPECTED_TID'"
```
Expected: count > 0 — confirming W3C TraceContext propagation works end-to-end through SigNoz.

- [ ] **Step 4: Open SigNoz UI**

`http://localhost:3301` → Services → click `tna-service` → see RED metrics, recent traces. Click any trace → span tree opens. Click "Go to logs" → log records for that trace appear.

- [ ] **Step 5: No commit (verification only)**

---

## Self-review checklist (run after all tasks complete)

- [ ] All 5 SigNoz containers running: `api`, `clickhouse`, `otel-collector`, `signoz-query-service`, `signoz-frontend`.
- [ ] `localhost:3301` shows SigNoz UI with `tna-service` listed.
- [ ] Triggering `/extract` produces traces in ClickHouse within 30s.
- [ ] Triggering `/extract` produces metrics in ClickHouse.
- [ ] Triggering `/extract` produces logs in ClickHouse, each carrying `trace_id`, `span_id`, `request_id`.
- [ ] W3C `traceparent` header on incoming request results in joined trace (same trace_id in SigNoz).
- [ ] All 209 unit/integration tests pass.
- [ ] No `prometheus_client`, `starlette_prometheus`, or `/metrics` references in `app/` or `tests/`.
- [ ] `prometheus/`, `loki/`, `promtail/`, `tempo/`, `grafana/` directories deleted.
- [ ] `docker-compose.override.yml.example` deleted.
- [ ] README, ARCHITECTURE, SPEC describe SigNoz only.
- [ ] Design doc status flipped to `Implemented`.
