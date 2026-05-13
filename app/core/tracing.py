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
"""
from __future__ import annotations
import os
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


def configure_tracing(service_name: str = "tna-service",
                     otlp_endpoint: str | None = None) -> None:
    """Initialise OTel SDK with OTLP gRPC export to Tempo.

    Endpoint defaults to TEMPO_OTLP_ENDPOINT env var, then to tempo:4317.
    Idempotent — repeated calls do nothing.
    """
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


def get_tracer(name: str = "tna_service"):
    return trace.get_tracer(name)
