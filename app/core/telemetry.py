"""Prometheus-style telemetry collectors, implemented on the OTel Metrics SDK.

Every collector name is preserved from the prometheus_client era. Labels are
now passed at call time as the `attributes` dict, e.g.:

    extractions_total.add(1, {"status": "success"})
    agent_duration_seconds.record(0.45, {"agent": "field_namer", "status": "success"})

The OTel MeterProvider is initialised in app/core/tracing.py and exports to
the configured OTLP endpoint every 15s. When the OTel SDK is not installed
(local dev), the noop fallback below makes every collector a silent no-op.
"""
from __future__ import annotations


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


# --- Extractions ---

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
    description="PLI count emitted per file.",
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


# --- Agents ---

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


# --- LLM provider ---

llm_calls_total = _m.create_counter(
    "llm_calls_total",
    description="Total LLM API invocations.",
)

llm_inference_duration_seconds = _m.create_histogram(
    "llm_inference_duration_seconds",
    description="Per-LLM-call duration.",
    unit="s",
)


# --- Tools ---

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


# --- Validators ---

validator_findings_total = _m.create_counter(
    "validator_findings_total",
    description="Validation findings emitted, by check + severity.",
)

# Back-compat alias — to be removed in Task 9 once validators are ported
validator_findings = validator_findings_total
