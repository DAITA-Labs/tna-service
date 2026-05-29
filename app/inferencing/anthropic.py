"""Anthropic SDK adapter — implements BaseProvider via tool-use completions."""
from __future__ import annotations

import json

from anthropic import Anthropic
from pydantic import BaseModel

from app.config.settings import get_settings
from app.core.logs import get_logger
from app.core.telemetry import (
    agent_tokens_input,
    agent_tokens_output,
    llm_calls_total,
)
from app.inferencing._base import BaseProvider, T


log = get_logger(__name__)


class MissingAPIKey(RuntimeError):
    """Raised when ANTHROPIC_API_KEY is not set."""


def _inline_refs(schema: dict, defs: dict | None = None) -> dict:
    """Recursively replace `{"$ref": "#/$defs/X"}` entries with the actual schema X.

    Anthropic tool-use otherwise emits nested objects as JSON-encoded strings,
    which Pydantic then rejects.
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


class AnthropicProvider(BaseProvider):
    """Anthropic SDK adapter using tool-use completions to enforce schemas."""

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

    def _call_provider(
        self, *, system: str, user: str,
        output_schema: type[T], tool_name: str,
    ):
        """Submit a tool-use completion to the Anthropic API.

        Records a failure counter and re-raises on any SDK error.
        """
        tool = schema_to_tool(tool_name, output_schema)
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

    def _record_usage(self, *, span, raw, agent_name: str) -> None:
        """Emit token-count metrics and span attributes from the response usage block."""
        usage = getattr(raw, "usage", None)
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

    def _extract_tokens(self, raw) -> tuple[int | None, int | None]:
        """Return `(input_tokens, output_tokens)` from `raw.usage`, or (None, None)."""
        usage = getattr(raw, "usage", None)
        if usage is None:
            return None, None
        return (
            getattr(usage, "input_tokens", None),
            getattr(usage, "output_tokens", None),
        )

    def _extract_raw_text(self, raw, tool_name: str) -> str:
        """Return a JSON-serialised string of the tool_use block's input dict."""
        for block in raw.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return json.dumps(block.input, default=str, sort_keys=True)
        return ""

    def _parse_response(
        self, *, raw, tool_name: str, output_schema: type[T],
    ) -> T:
        """Extract the tool_use block and instantiate `output_schema`."""
        for block in raw.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return output_schema(**block.input)
        raise RuntimeError(
            f"Anthropic returned no tool_use block for {tool_name!r}. "
            f"stop_reason={raw.stop_reason}; content={raw.content!r}"
        )


# Self-register with the provider factory so build_provider("anthropic") works.
# Importing this module triggers the registration; build_provider also forces
# the import as a safety net.
from app.inferencing.factory import register_provider  # noqa: E402

register_provider("anthropic", AnthropicProvider.from_env)
