"""AnthropicProvider emits the request/response span events and returns a tuple."""
from __future__ import annotations

from unittest.mock import MagicMock

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from pydantic import BaseModel

from app.inferencing.anthropic import AnthropicProvider


class _Out(BaseModel):
    val: int


def _fake_resp(in_tok: int, out_tok: int):
    block = MagicMock()
    block.type = "tool_use"
    block.name = "emit_test"
    block.input = {"val": 1}
    usage = MagicMock(input_tokens=in_tok, output_tokens=out_tok)
    return MagicMock(content=[block], stop_reason="tool_use", usage=usage)


def test_provider_records_request_and_response_events() -> None:
    exporter = InMemorySpanExporter()
    provider_tp = TracerProvider()
    provider_tp.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider_tp)

    client = MagicMock()
    client.messages.create.return_value = _fake_resp(10, 7)
    p = AnthropicProvider(client=client, model="claude-sonnet-4-6",
                          max_tokens=1024, temperature=0.0)

    parsed, raw_text, tin, tout = p.complete_with_schema(
        system="SYS", user="USR",
        output_schema=_Out, tool_name="emit_test",
        agent_name="t",
    )

    assert isinstance(parsed, _Out)
    assert raw_text  # non-empty JSON string
    assert tin == 10 and tout == 7

    llm_span = next(s for s in exporter.get_finished_spans()
                    if s.name == "llm.complete")
    names = [e.name for e in llm_span.events]
    assert "llm.request_sent" in names
    assert "llm.response_received" in names
