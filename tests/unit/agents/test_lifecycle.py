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


# ---------------------------------------------------------------------------
# T5: on_retry default structured log
# ---------------------------------------------------------------------------

def test_on_retry_default_logs_reason_and_attempt() -> None:
    """The default on_retry slot emits a structured log per retry."""
    from structlog.testing import capture_logs

    agent = _SemanticAgent(verdicts=[OutputVerdict.retry("nudge"), OutputVerdict.ok()])

    with capture_logs() as caps:
        result = agent.run(ctx=None, inputs=_DemoInputs(), provider=_PROVIDER)

    assert isinstance(result, _DemoOutput)
    retry_logs = [c for c in caps if c["event"] == "agent.retry_reason"]
    assert len(retry_logs) == 1
    assert retry_logs[0]["reason"] == "nudge"
    assert retry_logs[0]["attempt"] == 1


def test_on_retry_not_called_when_first_attempt_ok() -> None:
    """on_retry MUST NOT fire when validate_output returns ok on the first attempt."""
    from structlog.testing import capture_logs

    agent = _SemanticAgent(verdicts=[OutputVerdict.ok()])

    with capture_logs() as caps:
        agent.run(ctx=None, inputs=_DemoInputs(), provider=_PROVIDER)

    assert not any(c["event"] == "agent.retry_reason" for c in caps)


# ---------------------------------------------------------------------------
# T6: before_run / after_run fire on every exit path
# ---------------------------------------------------------------------------

class _ProbeAgent(_SemanticAgent):
    def __init__(self, verdicts: list[OutputVerdict]) -> None:
        super().__init__(verdicts)
        self.before_calls: list = []
        self.after_calls: list = []

    def before_run(self, ctx, inputs) -> None:
        self.before_calls.append((ctx, inputs))

    def after_run(self, result, attempts: int) -> None:
        self.after_calls.append((type(result).__name__, attempts))


class _ProbeAbortingAgent(_AbortingAgent):
    def __init__(self) -> None:
        self.before_calls: list = []
        self.after_calls: list = []

    def before_run(self, ctx, inputs) -> None:
        self.before_calls.append((ctx, inputs))

    def after_run(self, result, attempts: int) -> None:
        self.after_calls.append((type(result).__name__, attempts))


def test_before_and_after_run_fire_exactly_once_on_success() -> None:
    """Probe agent records before_run + after_run; both fire once on success."""
    agent = _ProbeAgent(verdicts=[OutputVerdict.ok()])
    agent.run(ctx=None, inputs=_DemoInputs(), provider=_PROVIDER)

    assert len(agent.before_calls) == 1
    assert len(agent.after_calls) == 1
    assert agent.after_calls[0][0] == "DemoOutput" or agent.after_calls[0][0] == "_DemoOutput"
    assert agent.after_calls[0][1] == 1  # one attempt


def test_before_and_after_run_fire_on_input_abort() -> None:
    """Both hooks still fire when validate_input aborts (no LLM call happens)."""
    agent = _ProbeAbortingAgent()
    agent.run(ctx=None, inputs=_DemoInputs(), provider=_PROVIDER)

    assert len(agent.before_calls) == 1
    assert len(agent.after_calls) == 1
    assert agent.after_calls[0][0] == "AgentRunFailure"
    assert agent.after_calls[0][1] == 0  # zero attempts (LLM never called)


def test_before_and_after_run_fire_on_retry_exhausted() -> None:
    """after_run receives the AgentRunFailure when budget is exhausted."""
    agent = _ProbeAgent(verdicts=[OutputVerdict.retry("bad 1"), OutputVerdict.retry("bad 2")])
    result = agent.run(ctx=None, inputs=_DemoInputs(), provider=_PROVIDER)

    assert isinstance(result, AgentRunFailure)
    assert len(agent.before_calls) == 1
    assert len(agent.after_calls) == 1
    assert agent.after_calls[0][0] == "AgentRunFailure"
    assert agent.after_calls[0][1] == 2  # both attempts consumed


# ---------------------------------------------------------------------------
# T7: Schema-fail on attempt 1 + semantic-retry on attempt 2 → exhausted
# ---------------------------------------------------------------------------

def test_schema_fail_then_semantic_retry_exhausts() -> None:
    """Schema error on attempt 1 → semantic retry verdict on attempt 2 → AgentRunFailure."""
    from pydantic import ValidationError

    class _OneBadOneGoodProvider(BaseProvider):
        """Raises ValidationError on the first call; returns canned model on second."""
        model = "fake"

        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def _call_provider(self, *, system, user, output_schema, tool_name):
            self.calls += 1
            if self.calls == 1:
                raise ValidationError.from_exception_data(
                    "Out", [{"type": "missing", "loc": ("value",), "input": {}}],
                )
            return output_schema(value="from-2nd-call")

        def _extract_tokens(self, raw):
            return None, None

        def _extract_raw_text(self, raw, tool_name):
            return ""

        def _record_usage(self, *, span, raw, agent_name):
            pass

        def _parse_response(self, *, raw, tool_name, output_schema):
            return raw

    provider = _OneBadOneGoodProvider()
    # The second attempt returns a parsed model; validate_output then asks for retry
    agent = _SemanticAgent(verdicts=[OutputVerdict.retry("not yet")])

    result = agent.run(ctx=None, inputs=_DemoInputs(), provider=provider)

    assert isinstance(result, AgentRunFailure)
    assert result.attempts == 2
    assert provider.calls == 2
