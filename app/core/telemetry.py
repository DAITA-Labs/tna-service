"""Prometheus collectors for the TNA service.

Per the spec's decision D10: per-phase + per-agent histograms; per-validator
counters; per-file gauges (PLI count, retry count, cost).

Imported by agents (services/agents/_base.py), applier (services/applier/),
validators (services/validation/), and the HTTP layer. The /metrics endpoint
exposes the default registry via starlette-prometheus.
"""
from prometheus_client import Counter, Histogram, Gauge


# Per-file extraction
extraction_duration_seconds = Histogram(
    "extraction_duration_seconds",
    "End-to-end extraction time for one workbook",
    labelnames=("format_detected",),
    buckets=(1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0),
)

extraction_pli_count = Gauge(
    "extraction_pli_count",
    "Number of PLIs extracted in the last run of this file",
    labelnames=("source_file",),
)

# Per-agent
agent_duration_seconds = Histogram(
    "agent_duration_seconds",
    "Wall-clock time spent inside one agent's LLM call",
    labelnames=("agent", "status"),
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 60.0),
)

agent_retry_count = Counter(
    "agent_retry_count",
    "Number of retries an agent performed",
    labelnames=("agent", "reason"),
)

agent_tokens_input = Counter(
    "agent_tokens_input",
    "Total input tokens consumed per agent + model",
    labelnames=("agent", "model"),
)

agent_tokens_output = Counter(
    "agent_tokens_output",
    "Total output tokens emitted per agent + model",
    labelnames=("agent", "model"),
)

# Per-validator
validator_findings_total = Counter(
    "validator_findings",
    "Validator findings emitted, by check and severity",
    labelnames=("check", "severity"),
)

# Per-phase extraction timing
extraction_phase_duration_seconds = Histogram(
    "extraction_phase_duration_seconds",
    "Per-phase latency within a single extraction request.",
    labelnames=("phase",),
)

# Per-tool
tool_calls_total = Counter(
    "tool_calls_total",
    "Total invocations of @tool-registered workbook tools.",
    labelnames=("tool_name",),
)

# Agent-level invocation counter
agent_calls_total = Counter(
    "agent_calls_total",
    "Total agent invocations.",
    labelnames=("agent", "status"),  # success | failure
)

# Extraction-level outcome counter
extractions_total = Counter(
    "extractions_total",
    "Total invocations of the extract() orchestrator.",
    labelnames=("status",),  # success | empty | failure
)

# LLM provider — isolates network time from agent loop time
llm_inference_duration_seconds = Histogram(
    "llm_inference_duration_seconds",
    "Time spent inside the LLM provider call (not including agent retry loop)",
    labelnames=("model",),
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 60.0),
)
