"""AgentRunner emits the input/validate/output span events + structured logs."""
from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from pydantic import BaseModel
from structlog.testing import capture_logs

from app.services.agents._base import AgentRunner, AgentSpec, RetryPolicy
from tests.fixtures.fake_llm import FakeLLM


class Out(BaseModel):
    val: int


def _spec() -> AgentSpec:
    return AgentSpec(
        name="dummy",
        system_prompt="SYS",
        output_schema=Out,
        build_user_input=lambda c, i: "USR",
        retry=RetryPolicy(max_retries=1),
    )


_EXPORTER = InMemorySpanExporter()
_TP = TracerProvider()
_TP.add_span_processor(SimpleSpanProcessor(_EXPORTER))
trace.set_tracer_provider(_TP)


@pytest.fixture(autouse=True)
def _reset_exporter():
    _EXPORTER.clear()
    yield


def test_capture_emits_all_required_events_for_one_call() -> None:
    llm = FakeLLM(canned={"Out": {"val": 1}}, raw_text="RAW", tokens_out=12)
    with capture_logs() as caps:
        out = AgentRunner(_spec(), llm).run(ctx=None, inputs={})
    assert isinstance(out, Out)

    spans = _EXPORTER.get_finished_spans()
    agent_span = next(s for s in spans if s.name == "agent.dummy")
    event_names = [e.name for e in agent_span.events]
    assert "input.system_prompt" in event_names
    assert "input.user_built" in event_names
    assert "llm.schema_validate" in event_names
    assert "output.parsed_ok" in event_names

    attrs = dict(agent_span.attributes)
    assert attrs["agent.name"] == "dummy"
    assert attrs["agent.status"] == "success"
    assert attrs["retries"] == 0

    log_events = {c["event"] for c in caps}
    assert "agent.input" in log_events
    assert "agent.response" in log_events
    assert "agent.output" in log_events


def test_capture_emits_attempt_2_events_on_retry() -> None:
    class FlipLLM:
        """Fails schema validation on first call, succeeds on second."""

        model = "fake"

        def __init__(self) -> None:
            self.calls = 0

        def complete_with_schema(self, *, system, user, output_schema,
                                  tool_name=None, agent_name="unknown",
                                  attempt=1):
            self.calls += 1
            if self.calls == 1:
                from pydantic import ValidationError
                raise ValidationError.from_exception_data(
                    "Out", [{"type": "missing", "loc": ("val",), "input": {}}],
                )
            return Out(val=99), "RAW2", 0, 5

    AgentRunner(_spec(), FlipLLM()).run(ctx=None, inputs={})

    agent_span = next(s for s in _EXPORTER.get_finished_spans()
                      if s.name == "agent.dummy")
    retries = [e for e in agent_span.events if e.name == "agent.retry"]
    assert len(retries) == 1
    assert retries[0].attributes["attempt"] == 2
    assert dict(agent_span.attributes)["retries"] == 1
