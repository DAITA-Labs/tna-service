"""Tool registry — @tool decorator registers a function under a name.

Tools are pure functions: take WorkbookCtx + typed args, return typed output.
Agents look them up by name when calling. Adding a tool is one file + one
decorator; no other place to wire it up.
"""
from __future__ import annotations
import functools
import time as _time
from collections.abc import Callable

from app.core.logs import get_logger
from app.core.telemetry import tool_calls_total, tool_duration_seconds, tool_errors_total

_tool_log = get_logger("app.workbook_tools")


class ToolRegistry:
    """Name → callable map. One instance is the global TOOL_REGISTRY."""

    def __init__(self):
        self._tools: dict[str, Callable] = {}

    def register(self, name: str) -> Callable:
        """Return a decorator that wraps `fn` with OTel instrumentation and stores it under `name`."""
        def decorator(fn: Callable) -> Callable:
            if name in self._tools:
                raise ValueError(f"tool {name!r} already registered")

            @functools.wraps(fn)
            def _counted(*args, **kwargs):
                tool_calls_total.add(1, {"tool_name": name})
                _t0 = _time.monotonic()
                _tool_log.debug("tool_call_start", tool_name=name)
                try:
                    result = fn(*args, **kwargs)
                    return result
                except Exception as exc:
                    _tool_log.warning("tool_call_failed", tool_name=name, error=str(exc))
                    tool_errors_total.add(1, {"tool_name": name})
                    raise
                finally:
                    tool_duration_seconds.record(
                        _time.monotonic() - _t0, {"tool_name": name}
                    )

            self._tools[name] = _counted
            return fn
        return decorator

    def get(self, name: str) -> Callable:
        """Return the instrumented callable for `name`, raising KeyError if absent."""
        if name not in self._tools:
            raise KeyError(f"tool {name!r} not registered")
        return self._tools[name]

    def names(self) -> list[str]:
        """Return all registered tool names in sorted order."""
        return sorted(self._tools.keys())


TOOL_REGISTRY = ToolRegistry()


def tool(name: str) -> Callable:
    """Register a function in the global TOOL_REGISTRY."""
    return TOOL_REGISTRY.register(name)


def get_tool(name: str) -> Callable:
    """Look up a registered tool by name, raising KeyError if absent."""
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[str]:
    """Return all registered tool names in sorted order."""
    return TOOL_REGISTRY.names()
