"""Health check router."""
from fastapi import APIRouter
from app.schemas.health import HealthResponse
from app.core.logs import get_logger

log = get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    log.info("health_check")
    return HealthResponse(status="healthy", version="0.1.0")


# The /metrics endpoint is wired separately in main.py via app.add_route()
# because starlette-prometheus' `metrics` is a Starlette endpoint, not a
# FastAPI route handler — including it here would need an adapter.
