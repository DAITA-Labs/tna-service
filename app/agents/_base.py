"""Agent base — single LLM call with schema-retry and lifecycle-hook slots.

The lifecycle hooks (`before_run`, `validate_input`, `validate_output`,
`after_run`, `on_retry`) are no-op slots; subclasses override them to
add gate behaviour. The retry-on-schema-failure loop preserves
today's `AgentRunner` semantics so migrating subclasses do not change
behaviour.
"""
from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from app.core.log_capture import log_agent_io
from app.core.logs import get_logger
from app.core.telemetry import agent_calls_total, agent_duration_seconds, agent_retry_count
from app.core.tracing import get_tracer
from app.inferencing._base import BaseProvider
from app.inferencing.capture import (
    record_input_event,
    record_output_event,
    record_retry_event,
    record_validate_event,
)
from app.inferencing.tuning import AgentTuning, render_prompt


log = get_logger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    """Immutable policy controlling how many extra retries are allowed on schema-validation failure."""

    max_retries: int = 1


@dataclass
class AgentRunFailure:
    """Returned (not raised) when all retry attempts are exhausted without a valid schema response."""

    agent_name: str
    attempts: int
    reason: str
    raw_outputs: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Verdict types
# ---------------------------------------------------------------------------

class _InputState(enum.Enum):
    OK = "ok"
    ABORT = "abort"


class _OutputState(enum.Enum):
    OK = "ok"
    RETRY = "retry"
    FAIL = "fail"


@dataclass(frozen=True)
class InputVerdict:
    """Verdict returned by `validate_input`; gates whether the LLM is called."""

    state: _InputState
    reason: str | None = None

    @classmethod
    def ok(cls) -> InputVerdict:
        return cls(state=_InputState.OK)

    @classmethod
    def abort(cls, reason: str) -> InputVerdict:
        return cls(state=_InputState.ABORT, reason=reason)

    @property
    def is_ok(self) -> bool:
        return self.state is _InputState.OK

    @property
    def is_abort(self) -> bool:
        return self.state is _InputState.ABORT


@dataclass(frozen=True)
class OutputVerdict:
    """Verdict returned by `validate_output`; gates whether the result is accepted or retried."""

    state: _OutputState
    reason: str | None = None

    @classmethod
    def ok(cls) -> OutputVerdict:
        return cls(state=_OutputState.OK)

    @classmethod
    def retry(cls, reason: str) -> OutputVerdict:
        return cls(state=_OutputState.RETRY, reason=reason)

    @classmethod
    def fail(cls, reason: str) -> OutputVerdict:
        return cls(state=_OutputState.FAIL, reason=reason)

    @property
    def is_ok(self) -> bool:
        return self.state is _OutputState.OK

    @property
    def is_retry(self) -> bool:
        return self.state is _OutputState.RETRY

    @property
    def is_fail(self) -> bool:
        return self.state is _OutputState.FAIL


# ---------------------------------------------------------------------------
# Agent base class
# ---------------------------------------------------------------------------

class Agent:
    """Closed-system base for one narrow LLM mapping job per subclass.

    Subclasses set the four class attributes (`name`, `prompt`, `output_schema`,
    `tuning`) and implement `build_input(ctx, inputs) -> str`. The lifecycle
    hooks are slots: override in subclasses to add per-agent gate behaviour;
    the defaults below are no-ops, preserving today's AgentRunner semantics.
    """

    name: str = ""
    prompt: str = ""
    output_schema: type[BaseModel]
    tuning: AgentTuning = AgentTuning()
    retry: RetryPolicy = RetryPolicy()
    tool_name: str | None = None

    def build_input(self, ctx: object, inputs: BaseModel) -> str:
        """Return the user-prompt text for this run. Subclasses must override."""
        raise NotImplementedError

    def validate_input(self, user_text: str) -> InputVerdict:
        """Return InputVerdict for `user_text`. Default: always ok (no-op slot)."""
        return InputVerdict.ok()

    def validate_output(self, output: BaseModel, ctx: object) -> OutputVerdict:
        """Return OutputVerdict for `output`. Default: always ok (no-op slot)."""
        return OutputVerdict.ok()

    def before_run(self, ctx: object, inputs: BaseModel) -> None:
        """Hook fired once before the first attempt. Default: no-op slot."""
        return None

    def after_run(self, result: BaseModel | AgentRunFailure, attempts: int) -> None:
        """Hook fired once after the final attempt. Default: no-op slot."""
        return None

    def on_retry(self, reason: str, attempt: int) -> None:
        """Hook fired before each retry attempt with the reason for retry. Default: no-op slot."""
        return None

    def run(
        self,
        ctx: object,
        inputs: BaseModel,
        provider: BaseProvider,
    ) -> BaseModel | AgentRunFailure:
        """Execute the agent and return the validated output or an `AgentRunFailure`."""
        self._provider = provider
        self.before_run(ctx, inputs)
        user = self.build_input(ctx, inputs)

        verdict = self.validate_input(user)
        if verdict.is_abort:
            failure = AgentRunFailure(
                agent_name=self.name,
                attempts=0,
                reason=verdict.reason or "input_aborted",
            )
            self.after_run(failure, 0)
            return failure

        result, attempts = self._run_with_retries(user, ctx)
        self.after_run(result, attempts)
        return result

    def _handle_schema_failure(
        self, span: object, exc: ValidationError, attempt: int, retries: int, user: str
    ) -> tuple[int, str]:
        """Handle a ValidationError from _invoke_provider; return updated (retries, user)."""
        reason = str(exc)
        record_validate_event(span, ok=False, error=reason[:200])
        agent_retry_count.add(1, {"agent": self.name, "reason": "schema_validation"})
        log.warning("agent_run_schema_validation_failed", agent=self.name, attempt=attempt, error=reason)
        if attempt > self.retry.max_retries:
            return retries, user
        retries += 1
        record_retry_event(span, attempt=attempt + 1, reason="schema_validation")
        user = _build_retry_prompt(user, reason)
        self.on_retry("schema_validation", attempt)
        return retries, user

    def _handle_post_parse(
        self,
        span: object,
        parsed: BaseModel,
        raw: str,
        tin: int,
        tout: int,
        retries: int,
        ctx: object,
        user: str,
        attempt: int,
        run_t0: float,
    ) -> tuple[BaseModel | AgentRunFailure | None, int, str, bool]:
        """Evaluate validate_output verdict; return (result, retries, user, should_continue)."""
        out_verdict = self.validate_output(parsed, ctx)
        if out_verdict.is_ok:
            record_validate_event(span, ok=True, error=None)
            self._emit_success_capture(span, parsed, raw, tin, tout, retries)
            self._record_success(attempt, span)
            notes = getattr(parsed, "decision_notes", None)
            if notes:
                log_agent_io(self.name, kind="decision_notes", payload=notes)
            return parsed, retries, user, False
        if out_verdict.is_fail:
            reason = out_verdict.reason or "output_failed"
            record_validate_event(span, ok=False, error=reason[:200])
            log.warning("agent_run_output_failed", agent=self.name, attempt=attempt, reason=reason)
            span.set_attribute("retries", retries)
            return self._record_failure(run_t0, attempt, reason, span), retries, user, False
        # is_retry
        reason = out_verdict.reason or "semantic_retry"
        record_validate_event(span, ok=False, error=reason[:200])
        agent_retry_count.add(1, {"agent": self.name, "reason": "semantic_validation"})
        log.warning("agent_run_semantic_retry", agent=self.name, attempt=attempt, reason=reason)
        if attempt > self.retry.max_retries:
            return AgentRunFailure(agent_name=self.name, attempts=attempt, reason=reason), retries, user, False
        retries += 1
        record_retry_event(span, attempt=attempt + 1, reason="semantic_validation")
        user = _build_retry_prompt(user, reason)
        self.on_retry(reason, attempt)
        return None, retries, user, True

    def _run_with_retries(self, user: str, ctx: object) -> tuple[BaseModel | AgentRunFailure, int]:
        """Drive the retry loop and return `(result, attempts)`."""
        tool_name = self.tool_name or f"emit_{self.name}"
        effective_system = render_prompt(self.prompt, tuning=self.tuning)
        attempt = 0
        retries = 0
        last_reason = ""
        run_t0 = time.monotonic()
        log.info("agent_run_start", agent=self.name)

        with get_tracer(__name__).start_as_current_span(f"agent.{self.name}") as span:
            span.set_attribute("agent.name", self.name)
            self._emit_input_capture(span, user)
            log_agent_io(self.name, kind="input", payload=user)

            while attempt <= self.retry.max_retries:
                attempt += 1
                try:
                    parsed, raw, tin, tout = self._invoke_provider(tool_name, user, effective_system)
                except ValidationError as exc:
                    last_reason = str(exc)
                    retries, user = self._handle_schema_failure(span, exc, attempt, retries, user)
                    if attempt > self.retry.max_retries:
                        break
                    continue
                except Exception as exc:
                    last_reason = f"{type(exc).__name__}: {exc}"
                    log.error("agent_run_unexpected_error", agent=self.name, error=last_reason)
                    if attempt > self.retry.max_retries:
                        break
                    continue

                result, retries, user, should_continue = self._handle_post_parse(
                    span, parsed, raw, tin, tout, retries, ctx, user, attempt, run_t0,
                )
                if not should_continue:
                    return result, attempt
                last_reason = result.reason if isinstance(result, AgentRunFailure) else ""

            span.set_attribute("retries", retries)
            failure = self._record_failure(run_t0, attempt, last_reason or "exhausted", span)
            return failure, attempt

    def _invoke_provider(self, tool_name: str, user: str, system: str | None = None) -> tuple[BaseModel, str, int, int]:
        """Call the LLM provider and return (parsed, raw_text, tokens_in, tokens_out)."""
        t0 = time.monotonic()
        result, raw, tin, tout = self._provider.complete_with_schema(
            system=system if system is not None else self.prompt,
            user=user,
            output_schema=self.output_schema,
            tool_name=tool_name,
            agent_name=self.name,
        )
        agent_duration_seconds.record(
            time.monotonic() - t0, {"agent": self.name, "status": "success"},
        )
        agent_calls_total.add(1, {"agent": self.name, "status": "success"})
        return result, raw, tin, tout

    def _emit_input_capture(self, span: object, user: str) -> None:
        """Emit input span events for system_prompt and user_built."""
        record_input_event(span, kind="system_prompt", text=self.prompt)
        record_input_event(span, kind="user_built", text=user, tools_used=None)

    def _emit_success_capture(
        self, span: object, result: BaseModel, raw: str,
        tin: int, tout: int, retries: int,
    ) -> None:
        """Emit success span attrs + structured logs."""
        record_output_event(span, schema_name=type(result).__name__)
        span.set_attribute("model", self._provider.model)
        span.set_attribute("tokens.in", tin)
        span.set_attribute("tokens.out", tout)
        span.set_attribute("retries", retries)
        log_agent_io(self.name, kind="response", payload=raw)
        log_agent_io(self.name, kind="output", payload=result.model_dump())

    def _record_success(self, attempt: int, span: object) -> None:
        """Log + tag span on success."""
        log.info("agent_run_success", agent=self.name, attempt=attempt)
        span.set_attribute("agent.status", "success")

    def _record_failure(
        self, run_t0: float, attempt: int, last_reason: str, span: object,
    ) -> AgentRunFailure:
        """Emit failure telemetry and return an AgentRunFailure for the caller."""
        agent_duration_seconds.record(
            time.monotonic() - run_t0, {"agent": self.name, "status": "failure"},
        )
        agent_calls_total.add(1, {"agent": self.name, "status": "failure"})
        span.set_attribute("agent.status", "failure")
        span.set_attribute("agent.error", str(last_reason)[:200])
        return AgentRunFailure(
            agent_name=self.name,
            attempts=attempt,
            reason=last_reason,
        )

    _provider: BaseProvider


def _build_retry_prompt(user: str, validation_error: str) -> str:
    """Append the previous attempt's validation error to the user prompt for the next retry."""
    return (
        user
        + "\n\n# Previous attempt failed validation:\n"
        + validation_error
        + "\n\nPlease emit a result that matches the schema exactly."
    )
