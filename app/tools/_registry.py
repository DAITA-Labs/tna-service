"""Tool registry — name to callable map for `@tool`-decorated helpers."""
from __future__ import annotations

import functools
import time
from collections.abc import Callable

from app.core.logs import get_logger
from app.core.telemetry import tool_calls_total, tool_duration_seconds, tool_errors_total


_log = get_logger("app.tools")


class ToolRegistry:
    """Name to callable map. The module-level `TOOL_REGISTRY` is the single instance."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}

    def register(self, name: str) -> Callable:
        """Return a decorator that wraps `fn` with OTel instrumentation and stores it under `name`."""
        def decorator(fn: Callable) -> Callable:
            if name in self._tools:
                raise ValueError(f"tool {name!r} already registered")

            @functools.wraps(fn)
            def _counted(*args, **kwargs):
                tool_calls_total.add(1, {"tool_name": name})
                t0 = time.monotonic()
                _log.debug("tool_call_start", tool_name=name)
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    _log.warning("tool_call_failed", tool_name=name, error=str(exc))
                    tool_errors_total.add(1, {"tool_name": name})
                    raise
                finally:
                    tool_duration_seconds.record(
                        time.monotonic() - t0, {"tool_name": name}
                    )

            self._tools[name] = _counted
            return fn
        return decorator

    def get(self, name: str) -> Callable:
        """Return the instrumented callable for `name`, raising KeyError if absent."""
        if name not in self._tools:
            raise KeyError(f"tool {name!r} not registered")
        return self._tools[name]

    def __getitem__(self, name: str) -> Callable:
        """Subscript form of `get` — `TOOL_REGISTRY[\"name\"]` is the preferred call site."""
        return self.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        """Return all registered tool names in sorted order."""
        return sorted(self._tools.keys())


TOOL_REGISTRY = ToolRegistry()


def get_tool(name: str) -> Callable:
    """Look up a registered tool by name, raising KeyError if absent."""
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[str]:
    """Return all registered tool names in sorted order."""
    return TOOL_REGISTRY.names()
