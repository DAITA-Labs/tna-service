"""Agent base — AgentSpec (data) + AgentRunner (one generic executor).

Each agent is an AgentSpec value: name, system prompt, Pydantic output schema,
a `build_user_input(ctx, inputs)` function. AgentRunner takes a spec + an
LLM provider and runs the call with retry-on-schema-validation-failure
(retry-with-error-context). Failures return AgentRunFailure rather than raise
— the orchestrator decides whether to halt or use a default.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.logs import get_logger
from app.core.telemetry import agent_calls_total, agent_duration_seconds, agent_retry_count
from app.core.tracing import get_tracer
from app.services.llm_provider import LLMProvider

log = get_logger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    """Immutable policy controlling how many extra retries are allowed on schema-validation failure."""

    max_retries: int = 1


@dataclass(frozen=True)
class AgentSpec:
    """Declarative, frozen description of one agent: prompts, schema, and retry policy."""

    name: str
    system_prompt: str
    output_schema: type[BaseModel]
    build_user_input: Callable[[Any, dict], str]  # Any: caller-defined context object
    tool_name: str | None = None  # defaults to f"emit_{name}" in runner
    retry: RetryPolicy = field(default_factory=RetryPolicy)


@dataclass
class AgentRunFailure:
    """Returned (not raised) when all retry attempts are exhausted without a valid schema response."""

    agent_name: str
    attempt_count: int
    final_error: str
    raw_outputs: list[str] = field(default_factory=list)


class AgentRunner:
    """Generic executor. One instance handles many runs of one spec."""

    def __init__(self, spec: AgentSpec, llm: LLMProvider) -> None:
        self.spec = spec
        self.llm = llm

    def run(self, ctx: Any, inputs: dict) -> BaseModel | AgentRunFailure:  # Any: caller-defined context object
        """Execute the agent with retry-on-schema-validation-failure, returning a parsed model or failure report."""
        tool_name = self.spec.tool_name or f"emit_{self.spec.name}"
        user = self.spec.build_user_input(ctx, inputs)
        attempt = 0
        last_error = ""
        run_t0 = time.monotonic()
        log.info("agent_run_start", agent=self.spec.name, input_keys=sorted(inputs.keys()))

        with get_tracer(__name__).start_as_current_span(f"agent.{self.spec.name}") as span:
            span.set_attribute("agent.name", self.spec.name)

            while attempt <= self.spec.retry.max_retries:
                attempt += 1
                try:
                    result = self._invoke_llm(tool_name, user)
                    self._record_attempt_success(run_t0, attempt, span)
                    return result
                except ValidationError as e:
                    last_error = str(e)
                    agent_retry_count.add(1, {"agent": self.spec.name, "reason": "schema_validation"})
                    log.warning("agent_run_schema_validation_failed",
                                agent=self.spec.name, attempt=attempt, error=last_error)
                    if attempt > self.spec.retry.max_retries:
                        break
                    user = _build_retry_prompt(user, last_error)
                except Exception as e:
                    last_error = f"{type(e).__name__}: {e}"
                    log.error("agent_run_unexpected_error", agent=self.spec.name, error=last_error)
                    if attempt > self.spec.retry.max_retries:
                        break

            return self._record_run_failure(run_t0, attempt, last_error, span)

    def _invoke_llm(self, tool_name: str, user: str) -> BaseModel:
        """Call the LLM provider and return a validated Pydantic model.

        Records per-attempt duration telemetry on success. Raises ValidationError
        or any provider exception on failure — callers handle retry logic.
        """
        t0 = time.monotonic()
        result = self.llm.complete_with_schema(
            system=self.spec.system_prompt,
            user=user,
            output_schema=self.spec.output_schema,
            tool_name=tool_name,
            agent_name=self.spec.name,
        )
        agent_duration_seconds.record(
            time.monotonic() - t0,
            {"agent": self.spec.name, "status": "success"},
        )
        agent_calls_total.add(1, {"agent": self.spec.name, "status": "success"})
        return result

    def _record_attempt_success(self, run_t0: float, attempt: int, span: object) -> None:
        """Log success and set span attributes after a successful attempt."""
        log.info("agent_run_success", agent=self.spec.name, attempt=attempt)
        span.set_attribute("agent.status", "success")

    def _record_run_failure(
        self, run_t0: float, attempt: int, last_error: str, span: object
    ) -> AgentRunFailure:
        """Record failure telemetry, set span attributes, and return an AgentRunFailure."""
        agent_duration_seconds.record(
            time.monotonic() - run_t0,
            {"agent": self.spec.name, "status": "failure"},
        )
        agent_calls_total.add(1, {"agent": self.spec.name, "status": "failure"})
        span.set_attribute("agent.status", "failure")
        span.set_attribute("agent.error", str(last_error)[:200])
        return AgentRunFailure(
            agent_name=self.spec.name,
            attempt_count=attempt,
            final_error=last_error,
        )


def _build_retry_prompt(user: str, validation_error: str) -> str:
    """Append the previous attempt's validation error to the user prompt for the next retry."""
    return (
        user
        + "\n\n# Previous attempt failed validation:\n"
        + validation_error
        + "\n\nPlease emit a result that matches the schema exactly."
    )
