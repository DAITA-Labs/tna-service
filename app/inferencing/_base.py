"""Provider protocol — the single surface every inferencing backend implements."""
from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class Provider(Protocol):
    """Interface for an LLM provider that returns a schema-validated Pydantic model."""

    model: str

    def complete_with_schema(
        self,
        *,
        system: str,
        user: str,
        output_schema: type[T],
        tool_name: str,
        agent_name: str = "unknown",
    ) -> T: ...
