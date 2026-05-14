"""Response shape for /health endpoint."""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Service readiness status with version identifier."""

    status: str
    version: str
