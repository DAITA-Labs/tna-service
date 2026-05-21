"""Agent generic base — single LLM call with schema-retry and lifecycle-hook slots.

The lifecycle hooks (`before_run`, `validate_input`, `validate_output`,
`after_run`, `on_retry`) default to no-ops. Sub-plan 3 fills them in. This
file preserves today's `AgentRunner` retry-on-schema-failure semantics so
migrating subclasses do not change behaviour.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.logs import get_logger
from app.core.telemetry import agent_calls_total, agent_duration_seconds, agent_retry_count
from app.core.tracing import get_tracer
from app.inferencing._base import Provider
from app.pipelines.tuning import Tuning


InputsT = TypeVar("InputsT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

log = get_logger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    """Immutable policy controlling how many extra retries are allowed on schema-validation failure."""

    max_retries: int = 1


@dataclass
class AgentRunFailure:
    """Returned (not raised) when all retry attempts are exhausted without a valid schema response."""

    agent_name: str
    attempt_count: int
    final_error: str
    raw_outputs: list[str] = field(default_factory=list)


class Agent(Generic[InputsT, OutputT]):
    """Closed-system base for one narrow LLM mapping job per subclass.

    Subclasses set the four class attributes (`name`, `prompt`, `output_schema`,
    `tuning`) and implement `build_input(ctx, inputs) -> str`. The lifecycle
    hooks are slots: override in subclasses to add per-agent gate behaviour;
    the defaults below are no-ops, preserving today's AgentRunner semantics.
    """

    name: str = ""
    prompt: str = ""
    output_schema: type[BaseModel]
    tuning: Tuning
    retry: RetryPolicy = RetryPolicy()
    tool_name: str | None = None

    def build_input(self, ctx: object, inputs: InputsT) -> str:
        """Return the user-prompt text for this run. Subclasses must override."""
        raise NotImplementedError

    def validate_input(self, user_text: str) -> bool:
        """Return True if `user_text` is acceptable. Default: always True (no-op slot)."""
        return True

    def validate_output(self, output: OutputT, ctx: object) -> bool:
        """Return True if `output` is semantically acceptable. Default: True (no-op slot)."""
        return True

    def before_run(self, ctx: object, inputs: InputsT) -> None:
        """Hook fired once before the first attempt. Default: no-op slot."""
        return None

    def after_run(self, result: OutputT | AgentRunFailure, attempts: int) -> None:
        """Hook fired once after the final attempt. Default: no-op slot."""
        return None

    def on_retry(self, reason: str, attempt: int) -> None:
        """Hook fired before each retry attempt with the reason for retry. Default: no-op slot."""
        return None

    def run(
        self,
        ctx: object,
        inputs: InputsT,
        provider: Provider,
    ) -> OutputT | AgentRunFailure:
        """Execute the agent and return the validated output or an `AgentRunFailure`."""
        self._provider = provider
        self.before_run(ctx, inputs)
        user = self.build_input(ctx, inputs)
        self.validate_input(user)

        result, attempts = self._run_with_retries(user)
        self.after_run(result, attempts)
        return result

    def _run_with_retries(self, user: str) -> tuple[OutputT | AgentRunFailure, int]:
        """Drive the retry loop and return `(result, attempts)`."""
        tool_name = self.tool_name or f"emit_{self.name}"
        attempt = 0
        last_error = ""
        run_t0 = time.monotonic()
        log.info("agent_run_start", agent=self.name)

        with get_tracer(__name__).start_as_current_span(f"agent.{self.name}") as span:
            span.set_attribute("agent.name", self.name)
            while attempt <= self.retry.max_retries:
                attempt += 1
                try:
                    parsed = self._invoke_provider(tool_name, user)
                    self._record_success(attempt, span)
                    return parsed, attempt
                except ValidationError as exc:
                    last_error = str(exc)
                    agent_retry_count.add(1, {"agent": self.name, "reason": "schema_validation"})
                    log.warning("agent_run_schema_validation_failed",
                                agent=self.name, attempt=attempt, error=last_error)
                    if attempt > self.retry.max_retries:
                        break
                    user = _build_retry_prompt(user, last_error)
                    self.on_retry("schema_validation", attempt)
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    log.error("agent_run_unexpected_error", agent=self.name, error=last_error)
                    if attempt > self.retry.max_retries:
                        break

            failure = self._record_failure(run_t0, attempt, last_error, span)
            return failure, attempt

    def _invoke_provider(self, tool_name: str, user: str) -> OutputT:
        """Call the LLM provider and return a parsed model. Raises on schema or SDK errors."""
        t0 = time.monotonic()
        out = self._provider.complete_with_schema(
            system=self.prompt,
            user=user,
            output_schema=self.output_schema,
            tool_name=tool_name,
            agent_name=self.name,
        )
        agent_duration_seconds.record(
            time.monotonic() - t0, {"agent": self.name, "status": "success"},
        )
        agent_calls_total.add(1, {"agent": self.name, "status": "success"})
        return out  # type: ignore[return-value]

    def _record_success(self, attempt: int, span: object) -> None:
        """Log + tag span on success."""
        log.info("agent_run_success", agent=self.name, attempt=attempt)
        span.set_attribute("agent.status", "success")

    def _record_failure(
        self, run_t0: float, attempt: int, last_error: str, span: object,
    ) -> AgentRunFailure:
        """Emit failure telemetry and return an AgentRunFailure for the caller."""
        agent_duration_seconds.record(
            time.monotonic() - run_t0, {"agent": self.name, "status": "failure"},
        )
        agent_calls_total.add(1, {"agent": self.name, "status": "failure"})
        span.set_attribute("agent.status", "failure")
        span.set_attribute("agent.error", str(last_error)[:200])
        return AgentRunFailure(
            agent_name=self.name,
            attempt_count=attempt,
            final_error=last_error,
        )

    # The `run` entry point above passes the provider through a transient
    # attribute so `_invoke_provider` can stay parameter-light. Set just
    # before each call; cleared on exit is unnecessary because each `run`
    # overwrites it.
    _provider: Provider

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)


def _build_retry_prompt(user: str, validation_error: str) -> str:
    """Append the previous attempt's validation error to the user prompt for the next retry."""
    return (
        user
        + "\n\n# Previous attempt failed validation:\n"
        + validation_error
        + "\n\nPlease emit a result that matches the schema exactly."
    )
