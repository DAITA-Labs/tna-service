"""Tests for app/services/agents/_base — retry-with-error-context semantics."""
from unittest.mock import MagicMock
from pydantic import BaseModel, ValidationError
from app.services.agents._base import (
    AgentSpec, AgentRunner, RetryPolicy, AgentRunFailure,
)


class DummyOut(BaseModel):
    val: int


def _spec(builder):
    return AgentSpec(
        name="dummy_agent",
        system_prompt="be brief",
        output_schema=DummyOut,
        build_user_input=builder,
        retry=RetryPolicy(max_retries=1),
    )


def test_runner_succeeds_first_attempt():
    fake_client = MagicMock()
    fake_client.complete_with_schema.return_value = DummyOut(val=42)
    fake_client.model = "claude-sonnet-4-6"
    spec = _spec(lambda ctx, inputs: "user prompt")
    runner = AgentRunner(spec, fake_client)
    out = runner.run(ctx=None, inputs={})
    assert isinstance(out, DummyOut)
    assert out.val == 42
    fake_client.complete_with_schema.assert_called_once()


def test_runner_retries_with_error_context_on_validation_failure():
    fake_client = MagicMock()
    fake_client.model = "claude-sonnet-4-6"
    fake_client.complete_with_schema.side_effect = [
        ValidationError.from_exception_data("DummyOut", [{
            "type": "missing", "loc": ("val",), "input": {},
        }]),
        DummyOut(val=99),
    ]
    spec = _spec(lambda ctx, inputs: "first prompt")
    runner = AgentRunner(spec, fake_client)
    out = runner.run(ctx=None, inputs={})
    assert isinstance(out, DummyOut)
    assert out.val == 99
    assert fake_client.complete_with_schema.call_count == 2
    # Retry must inject error context into the user prompt.
    second_kwargs = fake_client.complete_with_schema.call_args_list[1].kwargs
    assert "Previous attempt failed" in second_kwargs["user"]


def test_runner_returns_failure_when_retries_exhausted():
    fake_client = MagicMock()
    fake_client.model = "claude-sonnet-4-6"
    fake_client.complete_with_schema.side_effect = ValidationError.from_exception_data(
        "DummyOut", [{"type": "missing", "loc": ("val",), "input": {}}],
    )
    spec = _spec(lambda ctx, inputs: "p")
    runner = AgentRunner(spec, fake_client)
    result = runner.run(ctx=None, inputs={})
    assert isinstance(result, AgentRunFailure)
    assert result.agent_name == "dummy_agent"
    assert result.attempt_count == 2  # initial + 1 retry
