"""decision_notes appears as agent.decision_notes log when enabled, not when disabled."""
from __future__ import annotations

from structlog.testing import capture_logs

from app.artifacts.agent_io import AgentOutput
from app.inferencing.tuning import AgentTuning
from app.services.agents._base import AgentRunner, AgentSpec, RetryPolicy
from tests.fixtures.fake_llm import FakeLLM


class Out(AgentOutput):
    val: int


def test_decision_notes_logged_when_enabled() -> None:
    spec = AgentSpec(
        name="dummy",
        system_prompt="BASE",
        output_schema=Out,
        build_user_input=lambda c, i: "USR",
        retry=RetryPolicy(max_retries=1),
        tuning=AgentTuning(capture_decision_notes=True),
    )
    llm = FakeLLM(canned={"Out": {"val": 1, "decision_notes": "because"}})
    with capture_logs() as caps:
        AgentRunner(spec, llm).run(ctx=None, inputs={})
    assert any(c["event"] == "agent.decision_notes" for c in caps)


def test_decision_notes_not_logged_when_disabled() -> None:
    spec = AgentSpec(
        name="dummy",
        system_prompt="BASE",
        output_schema=Out,
        build_user_input=lambda c, i: "USR",
        retry=RetryPolicy(max_retries=1),
    )
    llm = FakeLLM(canned={"Out": {"val": 1}})
    with capture_logs() as caps:
        AgentRunner(spec, llm).run(ctx=None, inputs={})
    assert not any(c["event"] == "agent.decision_notes" for c in caps)
