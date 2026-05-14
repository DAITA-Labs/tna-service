"""OpenTelemetry tracing setup.

Initialized once at app startup via configure_tracing(). After that, anywhere
in the codebase can:

    from app.core.tracing import get_tracer
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("sheet", "S1")
        ...

Spans carry trace_id/span_id; the structlog processor in configure_logging
picks those up and attaches them to every log line for log-trace correlation.

All OTel imports are lazy (inside functions) so this module is safe to import
in environments where opentelemetry isn't installed (local dev outside
containers). Functions degrade gracefully to no-ops when OTel is absent.
"""
from __future__ import annotations

import os


_OTEL_SEVERITY = {
    "debug":     (5, "DEBUG"),
    "info":      (9, "INFO"),
    "warning":   (13, "WARN"),
    "warn":      (13, "WARN"),
    "error":     (17, "ERROR"),
    "exception": (17, "ERROR"),
    "critical":  (21, "FATAL"),
}


def configure_tracing(service_name: str = "tna-service",
                     otlp_endpoint: str | None = None):
    """Set up TracerProvider + MeterProvider + LoggerProvider with OTLP export.

    Returns the LoggerProvider for the caller to attach a stdlib handler.
    Returns None if OTel packages aren't available.

    Propagators: W3C TraceContext + B3 multi-format (composite).
    Outgoing httpx calls are auto-instrumented.
    Endpoint resolved from: argument -> OTEL_EXPORTER_OTLP_ENDPOINT ->
    TEMPO_OTLP_ENDPOINT (back-compat) -> http://otel-collector:4317.
    Idempotent — repeated calls return the existing LoggerProvider.
    """
    try:
        # lazy: opentelemetry is optional in local dev outside containers
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

    if trace.get_tracer_provider().__class__.__name__ != "ProxyTracerProvider":
        return _logs.get_logger_provider()

    endpoint = _resolve_otlp_endpoint(otlp_endpoint)
    resource = Resource.create({"service.name": service_name})

    _build_tracer_provider(
        endpoint, resource, trace, TracerProvider, BatchSpanProcessor, OTLPSpanExporter,
    )
    _build_meter_provider(
        endpoint, resource, metrics, MeterProvider, PeriodicExportingMetricReader, OTLPMetricExporter,
    )
    logger_provider = _build_logger_provider(
        endpoint, resource, _logs, LoggerProvider, BatchLogRecordProcessor, OTLPLogExporter,
    )
    _install_propagators()
    _install_httpx_instrumentation()
    return logger_provider


def _resolve_otlp_endpoint(arg: str | None) -> str:
    """Resolve the OTLP endpoint from arg, env, or the container default."""
    return (arg
            or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            or os.environ.get("TEMPO_OTLP_ENDPOINT")  # back-compat during SigNoz migration
            or "http://otel-collector:4317")


def _build_tracer_provider(endpoint, resource, trace, TracerProvider,
                           BatchSpanProcessor, OTLPSpanExporter):
    """Create a TracerProvider with a BatchSpanProcessor and register it globally."""
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=endpoint, insecure=True)
    ))
    trace.set_tracer_provider(tracer_provider)
    return tracer_provider


def _build_meter_provider(endpoint, resource, metrics, MeterProvider,
                          PeriodicExportingMetricReader, OTLPMetricExporter):
    """Create a MeterProvider with a periodic OTLP exporter and register it globally."""
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=15_000,
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )
    metrics.set_meter_provider(meter_provider)
    return meter_provider


def _build_logger_provider(endpoint, resource, _logs, LoggerProvider,
                           BatchLogRecordProcessor, OTLPLogExporter):
    """Create a LoggerProvider with a BatchLogRecordProcessor and register it globally."""
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(
        OTLPLogExporter(endpoint=endpoint, insecure=True)
    ))
    _logs.set_logger_provider(logger_provider)
    return logger_provider


def _install_propagators() -> None:
    """Install the composite W3C TraceContext + B3 multi-format propagator."""
    try:
        # lazy: propagator packages are optional alongside the core SDK
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
        from opentelemetry.propagators.b3 import B3MultiFormat
    except ImportError:
        return
    set_global_textmap(CompositePropagator([
        TraceContextTextMapPropagator(),
        B3MultiFormat(),
    ]))


def _install_httpx_instrumentation() -> None:
    """Auto-instrument httpx so outgoing Anthropic SDK calls propagate trace context."""
    try:
        # lazy: httpx instrumentation is an optional add-on
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    except ImportError:
        return
    HTTPXClientInstrumentor().instrument()


def get_tracer(name: str = "tna_service"):
    """Return an OTel tracer, or a no-op stand-in when OTel isn't installed."""
    try:
        from opentelemetry import trace
    except ImportError:
        return _NoopTracer()
    return trace.get_tracer(name)


class _NoopTracer:
    """Stand-in for an OTel Tracer when the SDK is not installed."""

    def start_as_current_span(self, name, **kwargs):
        return _NoopSpanCtx()

    def start_span(self, name, **kwargs):
        return _NoopSpan()


class _NoopSpanCtx:
    """Stand-in for an OTel span context manager when the SDK is not installed."""

    def __enter__(self):
        return _NoopSpan()

    def __exit__(self, *args):
        pass


class _NoopSpan:
    """Stand-in for an OTel Span when the SDK is not installed."""

    def set_attribute(self, key, value):
        pass

    def record_exception(self, exc, **kwargs):
        pass

    def set_status(self, status, **kwargs):
        pass

    def end(self):
        pass


def emit_to_otel_logs(logger, method_name, event_dict):
    """Structlog processor that side-emits every event to OTel logs over OTLP.

    Runs before JSONRenderer so the event is still a dict. Bypasses stdlib
    logging entirely — directly pushes a LogRecord through the SDK's global
    LoggerProvider. Returns the unchanged event_dict so the rest of the
    processor chain (JSON rendering to stdout) is unaffected.

    No-op when OTel SDK isn't installed or no LoggerProvider is configured.
    """
    try:
        import time
        from opentelemetry._logs import get_logger
        from opentelemetry.sdk._logs._internal import LogRecord
    except ImportError:
        return event_dict
    try:
        severity_number, severity_text = _OTEL_SEVERITY.get(
            method_name, (9, "INFO"))
        body = event_dict.get("event", "")
        attributes = {k: str(v) for k, v in event_dict.items() if k != "event"}
        ts_ns = int(time.time() * 1_000_000_000)
        get_logger("app").emit(LogRecord(
            timestamp=ts_ns,
            observed_timestamp=ts_ns,
            severity_number=severity_number,
            severity_text=severity_text,
            body=body,
            attributes=attributes,
        ))
    except Exception:
        pass  # best-effort: structlog must never crash if OTel emit fails
    return event_dict


def add_trace_context_to_log(logger, method_name, event_dict):
    """Structlog processor that injects current span's trace_id / span_id
    into every log record so log <-> trace correlation works in SigNoz.

    Lazy-imports opentelemetry so this module is safe to import in
    environments where OTel isn't installed (local dev outside containers).
    No-op when no active span or when OTel is uninitialised.
    """
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span is None:
            return event_dict
        ctx = span.get_span_context()
        if not ctx or not ctx.is_valid:
            return event_dict
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    except Exception:
        pass  # best-effort: structlog must never crash if trace lookup fails
    return event_dict
