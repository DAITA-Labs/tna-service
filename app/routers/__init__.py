"""FastAPI routers — one file per resource."""
from app.routers import extract, health

__all__ = ["extract", "health"]
