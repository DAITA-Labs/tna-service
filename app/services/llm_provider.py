"""LLM provider abstraction.

Defines the LLMProvider Protocol and the V1 AnthropicProvider implementation.
Single provider in V1 (per spec D5 / Q1 lock). Adding a fallback registry
later means a new file in app/services/ — no Protocol change.

Key responsibility: schema_to_tool inlines $defs / $ref before sending,
because Anthropic tool-use otherwise emits nested objects as JSON-encoded
strings and Pydantic rejects them.
"""
from __future__ import annotations
import time
from typing import Any, Protocol, TypeVar, runtime_checkable
from anthropic import Anthropic
from pydantic import BaseModel
from app.config.settings import get_settings
from app.core.logs import get_logger
from app.core.telemetry import llm_inference_duration_seconds

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
    """Protocol — any provider that can do schema-constrained completion."""
    model: str

    def complete_with_schema(
        self, *, system: str, user: str,
        output_schema: type[T], tool_name: str,
    ) -> T: ...


class AnthropicProvider:
    """V1 provider — Anthropic only.

    Caller passes system prompt, user message, and Pydantic schema.
    We wrap the schema in a tool definition and force the model to call it.
    """

    def __init__(self, client: Anthropic, model: str,
                 max_tokens: int = 4096, temperature: float = 0.0):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @classmethod
    def from_env(cls, api_key: str | None = None) -> "AnthropicProvider":
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
    ) -> T:
        tool = schema_to_tool(tool_name, output_schema)
        log.debug("llm_call_start", model=self.model, tool=tool_name,
                  system_chars=len(system), user_chars=len(user))
        t0 = time.monotonic()
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
        )
        llm_inference_duration_seconds.labels(model=self.model).observe(
            time.monotonic() - t0
        )

        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return output_schema(**block.input)

        raise RuntimeError(
            f"Anthropic returned no tool_use block for {tool_name!r}. "
            f"stop_reason={resp.stop_reason}; content={resp.content!r}"
        )
