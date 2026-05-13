"""OpenTelemetry tracing setup.

Initialized once at app startup via configure_tracing(). After that, anywhere
in the codebase can:

    from app.core.tracing import get_tracer
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("sheet", "S1")
        ...

Spans automatically carry trace_id/span_id; the structlog processor in
configure_logging picks those up and attaches them to every log line, so
Loki <-> Tempo correlation works without manual wiring.

All OTel imports are lazy (inside functions) so this module is safe to import
in environments where opentelemetry isn't installed (local dev outside
containers). Functions degrade gracefully to no-ops when OTel is absent.
"""
from __future__ import annotations
import os


def configure_tracing(service_name: str = "tna-service",
                     otlp_endpoint: str | None = None) -> None:
    """Initialise OTel SDK with OTLP gRPC export to Tempo + W3C/B3 propagation.

    Propagators: W3C TraceContext (default for browsers, FastAPI, most SDKs) +
    B3 multi-format (used by some legacy backends). Composite propagator
    accepts traceparent / X-B3-* headers on incoming requests and emits
    traceparent on outgoing calls.

    Outgoing HTTP calls via httpx (which the Anthropic SDK uses) are
    auto-instrumented so they inherit the current span and inject
    traceparent on the wire.

    Endpoint defaults to TEMPO_OTLP_ENDPOINT env var, then to tempo:4317.
    Idempotent — repeated calls do nothing.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    except ImportError:
        return

    if trace.get_tracer_provider().__class__.__name__ != "ProxyTracerProvider":
        # already configured
        return

    endpoint = (otlp_endpoint or os.environ.get("TEMPO_OTLP_ENDPOINT") or
                "http://tempo:4317")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=endpoint, insecure=True)
    ))
    trace.set_tracer_provider(provider)

    # Set up composite propagator: W3C TraceContext + B3 multi-format
    try:
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
        from opentelemetry.propagators.b3 import B3MultiFormat
        set_global_textmap(CompositePropagator([
            TraceContextTextMapPropagator(),  # W3C — incoming traceparent
            B3MultiFormat(),                  # B3 X-B3-* headers
        ]))
    except ImportError:
        # B3 propagator package optional; fall back to W3C only
        pass

    # Auto-instrument httpx so outgoing Anthropic SDK calls propagate trace context
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except ImportError:
        pass


def get_tracer(name: str = "tna_service"):
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return _NoopTracer()


class _NoopTracer:
    """Minimal stand-in when opentelemetry isn't installed."""

    def start_as_current_span(self, name, **kwargs):
        return _NoopSpanCtx()

    def start_span(self, name, **kwargs):
        return _NoopSpan()


class _NoopSpanCtx:
    def __enter__(self):
        return _NoopSpan()

    def __exit__(self, *args):
        pass


class _NoopSpan:
    def set_attribute(self, key, value):
        pass

    def record_exception(self, exc, **kwargs):
        pass

    def set_status(self, status, **kwargs):
        pass

    def end(self):
        pass


def add_trace_context_to_log(logger, method_name, event_dict):
    """Structlog processor that injects current span's trace_id / span_id
    into every log record so Grafana Loki <-> Tempo correlation works.

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
        pass
    return event_dict
