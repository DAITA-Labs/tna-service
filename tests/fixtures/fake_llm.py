"""LLMProvider stub for tests — returns canned values keyed by output schema name.

Mirrors the LLMProvider Protocol's complete_with_schema signature so the
production AgentRunner can use it without modification.
"""
from __future__ import annotations
from typing import Any


class FakeLLM:
    model: str = "fake"

    def __init__(self, canned: dict[str, dict],
                 raw_text: str = "{}",
                 tokens_in: int = 0, tokens_out: int = 0,
                 model: str = "fake") -> None:
        self._canned = canned
        self._raw = raw_text
        self._tokens_in = tokens_in
        self._tokens_out = tokens_out
        self.model = model
        self._scripted: list[dict] | None = None

    def script_responses(self, *responses: dict) -> "FakeLLM":
        """Configure an ordered queue of responses; one is popped per call. Chainable."""
        self._scripted = list(responses)
        return self

    def complete_with_schema(self, *, system: str, user: str,
                              output_schema: type, tool_name: str | None = None,
                              agent_name: str = "unknown",
                              attempt: int = 1) -> Any:
        if self._scripted is not None:
            if not self._scripted:
                raise AssertionError("FakeLLM script exhausted")
            payload = self._scripted.pop(0)
            return (output_schema(**payload), self._raw, self._tokens_in, self._tokens_out)
        name = output_schema.__name__
        if name not in self._canned:
            raise AssertionError(
                f"FakeLLM has no canned response for schema {name!r}. "
                f"Available: {sorted(self._canned)}"
            )
        return (output_schema(**self._canned[name]),
                self._raw, self._tokens_in, self._tokens_out)
