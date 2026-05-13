"""Tool registry — @tool decorator registers a function under a name.

Tools are pure functions: take WorkbookCtx + typed args, return typed output.
Agents look them up by name when calling. Adding a tool is one file + one
decorator; no other place to wire it up.
"""
from __future__ import annotations
import functools
import time as _time
from typing import Callable
from app.core.telemetry import tool_calls_total, tool_duration_seconds, tool_errors_total
from app.core.logs import get_logger

_tool_log = get_logger("app.workbook_tools")


class ToolRegistry:
    """Name → callable map. One instance is the global TOOL_REGISTRY."""

    def __init__(self):
        self._tools: dict[str, Callable] = {}

    def register(self, name: str) -> Callable:
        def decorator(fn: Callable) -> Callable:
            if name in self._tools:
                raise ValueError(f"tool {name!r} already registered")

            @functools.wraps(fn)
            def _counted(*args, **kwargs):
                tool_calls_total.labels(tool_name=name).inc()
                _t0 = _time.monotonic()
                _tool_log.debug("tool_call_start", tool_name=name)
                try:
                    result = fn(*args, **kwargs)
                    return result
                except Exception as exc:
                    _tool_log.warning("tool_call_failed", tool_name=name, error=str(exc))
                    tool_errors_total.labels(tool_name=name).inc()
                    raise
                finally:
                    tool_duration_seconds.labels(tool_name=name).observe(
                        _time.monotonic() - _t0
                    )

            self._tools[name] = _counted
            return fn
        return decorator

    def get(self, name: str) -> Callable:
        if name not in self._tools:
            raise KeyError(f"tool {name!r} not registered")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools.keys())


TOOL_REGISTRY = ToolRegistry()


def tool(name: str) -> Callable:
    """Register a function in the global TOOL_REGISTRY."""
    return TOOL_REGISTRY.register(name)


def get_tool(name: str) -> Callable:
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[str]:
    return TOOL_REGISTRY.names()
