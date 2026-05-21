"""`@tool` decorator — registers a function in the global TOOL_REGISTRY."""
from __future__ import annotations

from collections.abc import Callable

from app.tools._registry import TOOL_REGISTRY


def tool(name: str | None = None) -> Callable:
    """Register the decorated function in `TOOL_REGISTRY` under `name` (defaults to its `__name__`)."""
    def decorator(fn: Callable) -> Callable:
        registered_name = name or fn.__name__
        return TOOL_REGISTRY.register(registered_name)(fn)
    return decorator
