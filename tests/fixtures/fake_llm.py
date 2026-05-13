"""LLMProvider stub for tests — returns canned values keyed by output schema name.

Mirrors the LLMProvider Protocol's complete_with_schema signature so the
production AgentRunner can use it without modification.
"""
from __future__ import annotations
from typing import Any


class FakeLLM:
    def __init__(self, canned: dict[str, dict]):
        self._canned = canned

    def complete_with_schema(self, system: str, user: str,
                            output_schema: type, tool_name: str | None = None,
                            agent_name: str = "unknown") -> Any:
        name = output_schema.__name__
        if name not in self._canned:
            raise AssertionError(
                f"FakeLLM has no canned response for schema {name!r}. "
                f"Available: {sorted(self._canned)}"
            )
        return output_schema(**self._canned[name])
