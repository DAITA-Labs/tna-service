"""LLM provider abstraction.

Defines the LLMProvider Protocol and the AnthropicProvider implementation.
The Protocol allows agents to accept any conforming provider; the Anthropic
implementation is the only concrete provider in this service.

Key responsibility: schema_to_tool inlines $defs / $ref before sending,
because Anthropic tool-use otherwise emits nested objects as JSON-encoded
strings and Pydantic rejects them.
"""
from __future__ import annotations

import time
from typing import Protocol, TypeVar, runtime_checkable

from anthropic import Anthropic
from pydantic import BaseModel

from app.config.settings import get_settings
from app.core.logs import get_logger
from app.core.telemetry import (
    agent_tokens_input,
    agent_tokens_output,
    llm_calls_total,
    llm_inference_duration_seconds,
)
from app.core.tracing import get_tracer

T = TypeVar("T", bound=BaseModel)
log = get_logger(__name__)


class MissingAPIKey(RuntimeError):
    """Raised when ANTHROPIC_API_KEY is not set."""


def _inline_refs(schema: dict, defs: dict | None = None) -> dict:
    """Recursively replace {"$ref": "#/$defs/X"} with the actual schema X.

    Returns a new dict with no $defs / $ref remaining. Required so Anthropic
    tool-use sees a flat schema and emits proper nested objects (not strings).
    """
    if defs is None:
        defs = schema.get("$defs", {}) or schema.get("definitions", {}) or {}

    if isinstance(schema, dict):
        if "$ref" in schema and len(schema) == 1:
            ref = schema["$ref"]
            assert ref.startswith("#/$defs/") or ref.startswith("#/definitions/"), \
                f"unexpected $ref {ref!r}"
            name = ref.rsplit("/", 1)[-1]
            return _inline_refs(defs[name], defs)
        return {
            k: _inline_refs(v, defs)
            for k, v in schema.items()
            if k not in ("$defs", "definitions")
        }
    if isinstance(schema, list):
        return [_inline_refs(v, defs) for v in schema]
    return schema


def schema_to_tool(name: str, model: type[BaseModel]) -> dict:
    """Build an Anthropic tool definition that emits a Pydantic schema."""
    raw = model.model_json_schema()
    inlined = _inline_refs(raw)
    return {
        "name": name,
        "description": f"Emit a structured {model.__name__} result.",
        "input_schema": inlined,
    }


@runtime_checkable
class LLMProvider(Protocol):
    """Interface for an LLM provider that can complete with a Pydantic schema as output."""

    model: str

    def complete_with_schema(
        self, *, system: str, user: str,
        output_schema: type[T], tool_name: str,
        agent_name: str = "unknown",
    ) -> T: ...


class AnthropicProvider:
    """Anthropic SDK wrapper that drives schema-constrained tool-use completions."""

    def __init__(self, client: Anthropic, model: str,
                 max_tokens: int = 4096, temperature: float = 0.0):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @classmethod
    def from_env(cls, api_key: str | None = None) -> "AnthropicProvider":
        """Construct an AnthropicProvider from environment settings."""
        s = get_settings()
        key = api_key or s.anthropic_api_key
        if not key:
            raise MissingAPIKey(
                "ANTHROPIC_API_KEY is not set. Add it to .env (see .env.example)."
            )
        client = Anthropic(api_key=key)
        return cls(
            client=client, model=s.anthropic_model,
            max_tokens=s.max_tokens, temperature=s.temperature,
        )

    def complete_with_schema(
        self, *, system: str, user: str,
        output_schema: type[T], tool_name: str,
        agent_name: str = "unknown",
    ) -> T:
        """Call the Anthropic API and parse the response into output_schema."""
        tool = schema_to_tool(tool_name, output_schema)
        log.debug("llm_call_start", model=self.model, tool=tool_name,
                  system_chars=len(system), user_chars=len(user))
        t0 = time.monotonic()
        with get_tracer(__name__).start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.model", self.model)
            span.set_attribute("llm.agent", agent_name)
            resp = self._call_sdk(system=system, user=user, tool=tool, tool_name=tool_name)
            llm_inference_duration_seconds.record(
                time.monotonic() - t0, {"model": self.model}
            )
            llm_calls_total.add(1, {"model": self.model, "status": "success"})
            self._record_usage(span=span, resp=resp, agent_name=agent_name)
            return self._parse_tool_response(resp=resp, tool_name=tool_name, output_schema=output_schema)

    def _call_sdk(self, *, system: str, user: str, tool: dict, tool_name: str):
        """Submit the completion request to the Anthropic API.

        Records a failure counter and re-raises on any SDK error.
        """
        try:
            return self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
            )
        except Exception:
            llm_calls_total.add(1, {"model": self.model, "status": "failure"})
            raise

    def _record_usage(self, *, span, resp, agent_name: str) -> None:
        """Emit token-count metrics and span attributes from the response usage block."""
        usage = getattr(resp, "usage", None)
        inp_tokens: int | None = None
        out_tokens: int | None = None
        if usage is not None:
            inp_tokens = getattr(usage, "input_tokens", None)
            out_tokens = getattr(usage, "output_tokens", None)
            if isinstance(inp_tokens, int):
                agent_tokens_input.add(
                    inp_tokens, {"agent": agent_name, "model": self.model}
                )
                span.set_attribute("llm.input_tokens", inp_tokens)
            if isinstance(out_tokens, int):
                agent_tokens_output.add(
                    out_tokens, {"agent": agent_name, "model": self.model}
                )
                span.set_attribute("llm.output_tokens", out_tokens)
        log.info("llm_call_complete", model=self.model, agent=agent_name,
                 input_tokens=inp_tokens, output_tokens=out_tokens)

    def _parse_tool_response(self, *, resp, tool_name: str, output_schema: type[T]) -> T:
        """Extract the tool_use block from the response and instantiate output_schema.

        Raises RuntimeError if the model did not return a tool_use block.
        """
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return output_schema(**block.input)
        raise RuntimeError(
            f"Anthropic returned no tool_use block for {tool_name!r}. "
            f"stop_reason={resp.stop_reason}; content={resp.content!r}"
        )
