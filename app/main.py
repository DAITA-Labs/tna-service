"""FastAPI app entry point — wires routers + telemetry + structured logging."""
import os
from fastapi import FastAPI
from starlette_prometheus import metrics, PrometheusMiddleware
from app.config.settings import get_settings
from app.core.logs import configure_logging
from app.core.middleware import RequestIdMiddleware
from app.core.telemetry import extraction_duration_seconds  # noqa: F401 — register
from app.routers.extract import router as extract_router
from app.routers.health import router as health_router
from app.enums.environment import Environment


_settings = get_settings()
# JSON logs whenever we run inside a container (Loki / log-aggregator readable)
# OR whenever APP_ENV is non-development. Local `make serve` outside a container
# still gets the human-readable ConsoleRenderer.
_in_container = os.path.exists("/.dockerenv") or os.environ.get("LOG_FORMAT") == "json"
configure_logging(
    level=_settings.log_level,
    json_output=_in_container or _settings.app_env != Environment.DEVELOPMENT,
)

from app.core.tracing import configure_tracing
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Tracing must be initialized BEFORE FastAPI auto-instrumentation.
_tracing_enabled = _in_container or os.environ.get("OTEL_ENABLED", "").lower() in ("1", "true", "yes")
if _tracing_enabled:
    configure_tracing(service_name="tna-service")

app = FastAPI(title="TNA Service", version="0.1.0")

if _tracing_enabled:
    FastAPIInstrumentor.instrument_app(app)

app.add_middleware(PrometheusMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_route("/metrics", metrics)
app.include_router(extract_router)
app.include_router(health_router)
