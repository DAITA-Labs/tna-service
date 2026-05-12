"""Tests for app/services/llm_provider — $ref inlining + provider behaviour."""
import json
import pytest
from unittest.mock import MagicMock
from pydantic import BaseModel
from app.services.llm_provider import (
    AnthropicProvider, MissingAPIKey, schema_to_tool, _inline_refs,
)


class DummyOut(BaseModel):
    name: str
    count: int


def test_schema_to_tool_inlines_refs():
    """Nested model schema must be inlined — Anthropic mishandles $ref."""
    class Inner(BaseModel):
        x: int

    class Outer(BaseModel):
        inner: Inner

    tool_schema = schema_to_tool("emit_outer", Outer)
    assert "$defs" not in tool_schema["input_schema"]
    assert "$ref" not in json.dumps(tool_schema)


def test_inline_refs_resolves_definitions():
    raw = {
        "$defs": {"Foo": {"type": "object", "properties": {"a": {"type": "integer"}}}},
        "type": "object",
        "properties": {"foo": {"$ref": "#/$defs/Foo"}},
    }
    inlined = _inline_refs(raw)
    assert "$defs" not in inlined
    assert inlined["properties"]["foo"]["type"] == "object"


def test_anthropic_provider_raises_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    # Also override get_settings cache to ensure clean state.
    from app.config import settings as cfg
    cfg.get_settings.cache_clear()
    with pytest.raises(MissingAPIKey):
        AnthropicProvider.from_env(api_key=None)


def test_anthropic_provider_complete_with_schema_calls_client():
    fake_client = MagicMock()
    fake_block = MagicMock()
    fake_block.type = "tool_use"
    fake_block.name = "emit_dummy"
    fake_block.input = {"name": "abc", "count": 7}
    fake_resp = MagicMock()
    fake_resp.content = [fake_block]
    fake_resp.stop_reason = "tool_use"
    fake_client.messages.create.return_value = fake_resp

    p = AnthropicProvider(client=fake_client, model="claude-sonnet-4-6")
    out = p.complete_with_schema(
        system="be brief",
        user="extract this",
        output_schema=DummyOut,
        tool_name="emit_dummy",
    )
    assert isinstance(out, DummyOut)
    assert out.name == "abc"
    assert out.count == 7
