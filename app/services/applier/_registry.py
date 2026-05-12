"""Pattern registry — maps BoundaryPattern to a `pli_rows(ctx, boundaries)`
handler function. Adding a new pattern is one file + one decorator."""
from __future__ import annotations
from typing import Callable


HandlerFn = Callable  # (ctx, boundaries) -> list[int]


class PatternRegistry:
    def __init__(self):
        self._handlers: dict[str, HandlerFn] = {}

    def register(self, pattern: str) -> Callable:
        def decorator(fn: HandlerFn) -> HandlerFn:
            if pattern in self._handlers:
                raise ValueError(f"pattern {pattern!r} already registered")
            self._handlers[pattern] = fn
            return fn
        return decorator

    def get(self, pattern: str) -> HandlerFn:
        if pattern not in self._handlers:
            raise KeyError(f"pattern {pattern!r} not registered")
        return self._handlers[pattern]

    def names(self) -> list[str]:
        return sorted(self._handlers.keys())


PATTERN_REGISTRY = PatternRegistry()


def pattern_handler(pattern: str) -> Callable:
    return PATTERN_REGISTRY.register(pattern)


def get_pattern_handler(pattern: str) -> HandlerFn:
    return PATTERN_REGISTRY.get(pattern)


def list_patterns() -> list[str]:
    return PATTERN_REGISTRY.names()
