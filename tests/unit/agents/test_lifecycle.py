"""Lifecycle gate tests: validate_input abort, validate_output ok/fail/retry paths."""
from __future__ import annotations

from pydantic import BaseModel

from app.agents._base import Agent, AgentRunFailure, InputVerdict, OutputVerdict
from app.inferencing._base import BaseProvider


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

class _DemoOutput(BaseModel):
    value: str


class _FakeProvider(BaseProvider):
    model = "fake"

    def _call_provider(self, *, system, user, output_schema, tool_name):
        return output_schema(value="hello")

    def _extract_tokens(self, raw):
        return None, None

    def _extract_raw_text(self, raw, tool_name):
        return ""

    def _record_usage(self, *, span, raw, agent_name):
        pass

    def _parse_response(self, *, raw, tool_name, output_schema):
        return raw


_PROVIDER = _FakeProvider()


class _DemoInputs(BaseModel):
    data: str = "test"


# ---------------------------------------------------------------------------
# Aborting agent
# ---------------------------------------------------------------------------

class _AbortingAgent(Agent):
    name = "aborting"
    prompt = "system"
    output_schema = _DemoOutput

    def build_input(self, ctx, inputs):
        return inputs.data

    def validate_input(self, user_text):
        return InputVerdict.abort("input is not acceptable")


# ---------------------------------------------------------------------------
# Semantic agent with queued verdicts
# ---------------------------------------------------------------------------

class _SemanticAgent(Agent):
    name = "semantic"
    prompt = "system"
    output_schema = _DemoOutput

    def __init__(self, verdicts: list[OutputVerdict]) -> None:
        self._verdicts = list(verdicts)

    def build_input(self, ctx, inputs):
        return inputs.data

    def validate_output(self, output, ctx):
        return self._verdicts.pop(0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_abort_path_skips_llm_and_returns_failure():
    agent = _AbortingAgent()
    result = agent.run(ctx=None, inputs=_DemoInputs(), provider=_PROVIDER)
    assert isinstance(result, AgentRunFailure)
    assert result.reason == "input is not acceptable"
    assert result.attempts == 0


def test_semantic_ok_first_attempt_returns_model():
    agent = _SemanticAgent([OutputVerdict.ok()])
    result = agent.run(ctx=None, inputs=_DemoInputs(), provider=_PROVIDER)
    assert isinstance(result, _DemoOutput)
    assert result.value == "hello"


def test_semantic_fail_returns_failure_immediately_no_retry():
    agent = _SemanticAgent([OutputVerdict.fail("hard failure")])
    result = agent.run(ctx=None, inputs=_DemoInputs(), provider=_PROVIDER)
    assert isinstance(result, AgentRunFailure)
    assert result.reason == "hard failure"
    assert result.attempts == 1


def test_retry_then_ok_returns_model_on_second_attempt():
    agent = _SemanticAgent([OutputVerdict.retry("try again"), OutputVerdict.ok()])
    result = agent.run(ctx=None, inputs=_DemoInputs(), provider=_PROVIDER)
    assert isinstance(result, _DemoOutput)
    assert result.value == "hello"


def test_retry_exhausted_returns_failure():
    agent = _SemanticAgent([OutputVerdict.retry("bad 1"), OutputVerdict.retry("bad 2")])
    result = agent.run(ctx=None, inputs=_DemoInputs(), provider=_PROVIDER)
    assert isinstance(result, AgentRunFailure)
    assert result.attempts == 2
