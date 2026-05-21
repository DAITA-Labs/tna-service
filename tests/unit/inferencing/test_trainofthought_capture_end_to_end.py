"""End-to-end coverage of capture events + logs for one agent call."""
from __future__ import annotations

from structlog.testing import capture_logs

from app.artifacts.agent_io import AgentOutput
from app.services.agents._base import AgentRunner, AgentSpec, RetryPolicy
from tests.conftest import SPAN_EXPORTER
from tests.fixtures.fake_llm import FakeLLM


class Out(AgentOutput):
    val: int


def test_one_llm_call_emits_full_event_set_and_log_set() -> None:
    spec = AgentSpec(
        name="dummy",
        system_prompt="SYS",
        output_schema=Out,
        build_user_input=lambda c, i: "USR",
        retry=RetryPolicy(max_retries=1),
    )
    llm = FakeLLM(canned={"Out": {"val": 1}}, raw_text="RAW",
                  tokens_in=10, tokens_out=7)

    with capture_logs() as caps:
        AgentRunner(spec, llm).run(ctx=None, inputs={})

    events = {e.name for s in SPAN_EXPORTER.get_finished_spans() for e in s.events}
    required_events = {
        "input.system_prompt", "input.user_built",
        "llm.schema_validate", "output.parsed_ok",
    }
    assert required_events.issubset(events), \
        f"missing events: {required_events - events}"

    log_events = {c["event"] for c in caps}
    assert {"agent.input", "agent.response", "agent.output"}.issubset(log_events), \
        f"missing logs: {{'agent.input','agent.response','agent.output'}} - log_events"
