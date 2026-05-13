"""Agent base — AgentSpec (data) + AgentRunner (one generic executor).

Each agent is an AgentSpec value: name, system prompt, Pydantic output schema,
a `build_user_input(ctx, inputs)` function. AgentRunner takes a spec + an
LLM provider and runs the call with retry-on-schema-validation-failure
(retry-with-error-context). Failures return AgentRunFailure rather than raise
— the orchestrator decides whether to halt or use a default.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from pydantic import BaseModel, ValidationError
from app.services.llm_provider import LLMProvider
from app.core.logs import get_logger
from app.core.telemetry import agent_duration_seconds, agent_retry_count

log = get_logger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    """How many extra retries on schema validation failure. Default 1."""
    max_retries: int = 1


@dataclass(frozen=True)
class AgentSpec:
    """Declarative agent definition. Frozen — agents are values."""
    name: str
    system_prompt: str
    output_schema: type[BaseModel]
    build_user_input: Callable[[Any, dict], str]
    tool_name: str | None = None  # defaults to f"emit_{name}" in runner
    retry: RetryPolicy = field(default_factory=RetryPolicy)


@dataclass
class AgentRunFailure:
    """Returned (not raised) when the agent's retries are exhausted."""
    agent_name: str
    attempt_count: int
    final_error: str
    raw_outputs: list[str] = field(default_factory=list)


class AgentRunner:
    """Generic executor. One instance handles many runs of one spec."""

    def __init__(self, spec: AgentSpec, llm: LLMProvider):
        self.spec = spec
        self.llm = llm

    def run(self, ctx: Any, inputs: dict) -> BaseModel | AgentRunFailure:
        tool_name = self.spec.tool_name or f"emit_{self.spec.name}"
        user = self.spec.build_user_input(ctx, inputs)
        attempt = 0
        last_error = ""
        log.info("agent_run_start", agent=self.spec.name,
                 input_keys=sorted(inputs.keys()))

        while attempt <= self.spec.retry.max_retries:
            attempt += 1
            t0 = time.monotonic()
            try:
                out = self.llm.complete_with_schema(
                    system=self.spec.system_prompt,
                    user=user,
                    output_schema=self.spec.output_schema,
                    tool_name=tool_name,
                    agent_name=self.spec.name,
                )
                agent_duration_seconds.labels(agent=self.spec.name).observe(
                    time.monotonic() - t0
                )
                log.info("agent_run_success", agent=self.spec.name,
                         attempt=attempt)
                return out
            except ValidationError as e:
                last_error = str(e)
                agent_retry_count.labels(
                    agent=self.spec.name, reason="schema_validation"
                ).inc()
                log.warning("agent_run_schema_validation_failed",
                            agent=self.spec.name, attempt=attempt, error=last_error)
                if attempt > self.spec.retry.max_retries:
                    break
                user = (
                    user
                    + "\n\n# Previous attempt failed validation:\n"
                    + last_error
                    + "\n\nPlease emit a result that matches the schema exactly."
                )
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                log.error("agent_run_unexpected_error",
                          agent=self.spec.name, error=last_error)
                if attempt > self.spec.retry.max_retries:
                    break

        return AgentRunFailure(
            agent_name=self.spec.name,
            attempt_count=attempt,
            final_error=last_error,
        )
