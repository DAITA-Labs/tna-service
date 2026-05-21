"""Service layer — orchestration between the HTTP boundary and the Haystack pipeline."""
from app.services.extract_service import extract

__all__ = ["extract"]
