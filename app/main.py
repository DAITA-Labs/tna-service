"""FastAPI app entry point — wires routers + telemetry + structured logging."""
from fastapi import FastAPI
from starlette_prometheus import metrics, PrometheusMiddleware
from app.config.settings import get_settings
from app.core.logs import configure_logging
from app.core.telemetry import extraction_duration_seconds  # noqa: F401 — register
from app.routers.extract import router as extract_router
from app.routers.health import router as health_router
from app.enums.environment import Environment


_settings = get_settings()
configure_logging(
    level=_settings.log_level,
    json_output=_settings.app_env != Environment.DEVELOPMENT,
)


app = FastAPI(title="TNA Service", version="0.1.0")
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)
app.include_router(extract_router)
app.include_router(health_router)
