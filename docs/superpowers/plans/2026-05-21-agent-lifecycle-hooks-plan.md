# Agent Lifecycle Hooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the lifecycle slots from sub-plan 1 (no-op defaults) into real behaviour, so any agent subclass can plug in semantic validation that gates the LLM verdict before downstream code uses it.

**Architecture:** Three new call sites in `Agent.run` — `validate_input` (pre-LLM), `validate_output` (post-parse), `on_retry` (between attempts). Verdict types: `InputVerdict.ok() | abort(reason)`, `OutputVerdict.ok() | retry(reason) | fail(reason)`. Retry-with-reason follows the same shape as today's schema-validation retry: reason text appended to user prompt for the next call. Budget cap at `max_retries=1` — at most two LLM calls per `Agent.run` invocation.

**Tech Stack:** Python 3.12, Pydantic 2.6+. No new external dependencies.

---

## Conventions

- Python 3.12+, modern types (`X | Y`, `list[...]`, etc.).
- `from __future__ import annotations` at the top of every new module.
- One-line imperative docstrings; ≤40-line functions; no narrative comments.
- Conventional commits: `feat(agents):`, `test(agents):`, `docs(principles):`.
- `make test` green after every commit.
- TDD per task: write the failing test first, run it to confirm red, implement, run it to confirm green, then commit.

## Spec coverage map

| Spec §5 / §9 requirement                                                                          | Task |
|---------------------------------------------------------------------------------------------------|------|
| `validate_input(user_text)` is a real call site after `build_input`                               | T2   |
| `InputVerdict.ok()` / `InputVerdict.abort(reason)`                                                | T1   |
| `validate_output(output, ctx)` is a real call site after parsing                                  | T3   |
| `OutputVerdict.ok()` / `OutputVerdict.retry(reason)` / `OutputVerdict.fail(reason)`               | T1   |
| Schema-fail and semantic-fail share one `attempts` budget                                         | T4   |
| Default `RetryPolicy.max_retries = 1` → max 2 LLM calls per run                                   | T4   |
| `on_retry(reason, attempt)` slot fires before each retry; default emits span event + log         | T5   |
| `before_run(ctx, inputs)` / `after_run(result, attempts)` fire at entry/exit; default no-op       | T6   |
| Unit tests for every verdict combination                                                          | T7   |
| Test file home: `tests/unit/agents/test_lifecycle.py`; primitives file keeps the no-op assertions | T8   |
| `FakeLLM.script_responses(*responses)` extension                                                  | T9   |
| Principle 12 — Agent lifecycle is a closed system                                                 | T10  |

---

## T1 — Verdict dataclasses

- [ ] Write a failing test `tests/unit/agents/test_verdicts.py` that asserts the verdict constructors and predicates exist and behave.

  ```python
  # tests/unit/agents/test_verdicts.py
  from __future__ import annotations

  from app.agents._base import InputVerdict, OutputVerdict


  def test_input_verdict_ok_is_not_abort() -> None:
      v = InputVerdict.ok()
      assert v.is_ok is True
      assert v.is_abort is False
      assert v.reason is None


  def test_input_verdict_abort_carries_reason() -> None:
      v = InputVerdict.abort("empty user text")
      assert v.is_ok is False
      assert v.is_abort is True
      assert v.reason == "empty user text"


  def test_output_verdict_states_are_mutually_exclusive() -> None:
      ok = OutputVerdict.ok()
      retry = OutputVerdict.retry("row index out of range")
      fail = OutputVerdict.fail("hard semantic violation")

      assert (ok.is_ok, ok.is_retry, ok.is_fail) == (True, False, False)
      assert (retry.is_ok, retry.is_retry, retry.is_fail) == (False, True, False)
      assert (fail.is_ok, fail.is_retry, fail.is_fail) == (False, False, True)

      assert retry.reason == "row index out of range"
      assert fail.reason == "hard semantic violation"
      assert ok.reason is None
  ```

- [ ] Run `pytest tests/unit/agents/test_verdicts.py -q` → expect red.
- [ ] Implement the dataclasses in `app/agents/_base.py` (append to the file sub-plan 1 created).

  ```python
  # app/agents/_base.py — add near the top, after existing imports
  from __future__ import annotations

  from dataclasses import dataclass
  from enum import Enum


  class _InputState(str, Enum):
      OK = "ok"
      ABORT = "abort"


  class _OutputState(str, Enum):
      OK = "ok"
      RETRY = "retry"
      FAIL = "fail"


  @dataclass(frozen=True)
  class InputVerdict:
      """Pre-LLM gate verdict produced by Agent.validate_input."""

      state: _InputState
      reason: str | None = None

      @classmethod
      def ok(cls) -> InputVerdict:
          """Accept the built user text and proceed to the LLM call."""
          return cls(state=_InputState.OK)

      @classmethod
      def abort(cls, reason: str) -> InputVerdict:
          """Refuse the run before any LLM call; caller receives AgentRunFailure."""
          return cls(state=_InputState.ABORT, reason=reason)

      @property
      def is_ok(self) -> bool:
          """True when the input passed pre-LLM validation."""
          return self.state is _InputState.OK

      @property
      def is_abort(self) -> bool:
          """True when the input failed pre-LLM validation."""
          return self.state is _InputState.ABORT


  @dataclass(frozen=True)
  class OutputVerdict:
      """Post-parse gate verdict produced by Agent.validate_output."""

      state: _OutputState
      reason: str | None = None

      @classmethod
      def ok(cls) -> OutputVerdict:
          """Accept the parsed output and return it from Agent.run."""
          return cls(state=_OutputState.OK)

      @classmethod
      def retry(cls, reason: str) -> OutputVerdict:
          """Request another LLM call with reason appended to the user prompt."""
          return cls(state=_OutputState.RETRY, reason=reason)

      @classmethod
      def fail(cls, reason: str) -> OutputVerdict:
          """Hard-fail without retry; caller receives AgentRunFailure."""
          return cls(state=_OutputState.FAIL, reason=reason)

      @property
      def is_ok(self) -> bool:
          """True when the parsed output passed semantic validation."""
          return self.state is _OutputState.OK

      @property
      def is_retry(self) -> bool:
          """True when the parsed output asked for a retry-with-reason."""
          return self.state is _OutputState.RETRY

      @property
      def is_fail(self) -> bool:
          """True when the parsed output is unsalvageable."""
          return self.state is _OutputState.FAIL
  ```

- [ ] Re-run `pytest tests/unit/agents/test_verdicts.py -q` → expect green.
- [ ] Run `make test` → expect green.
- [ ] Commit: `feat(agents): add InputVerdict and OutputVerdict types`

## T2 — `validate_input` call site

- [ ] Write a failing test in `tests/unit/agents/test_lifecycle.py` that aborts before the LLM is ever called.

  ```python
  # tests/unit/agents/test_lifecycle.py
  from __future__ import annotations

  from typing import Any

  from app.agents._base import Agent, AgentRunFailure, InputVerdict, OutputVerdict
  from tests.fixtures.fake_llm import FakeLLM


  class _AbortingAgent(Agent):
      """Test agent that aborts before any LLM call."""

      name = "abort_demo"
      system_prompt = "system"
      output_schema = _DemoOutput  # defined below

      def build_input(self, ctx: Any, inputs: dict) -> str:
          """Return a fixed user text."""
          return "hello"

      def validate_input(self, user_text: str) -> InputVerdict:
          """Abort whenever called."""
          return InputVerdict.abort("user text not allowed")


  def test_validate_input_abort_short_circuits_llm() -> None:
      llm = FakeLLM(canned={})  # no canned responses — LLM must NOT be called
      agent = _AbortingAgent(llm=llm)

      result = agent.run(ctx=None, inputs={})

      assert isinstance(result, AgentRunFailure)
      assert result.reason == "user text not allowed"
      assert result.attempts == 0
  ```

  Plus a tiny `_DemoOutput` Pydantic model at the top of the file:

  ```python
  from pydantic import BaseModel


  class _DemoOutput(BaseModel):
      value: str
  ```

- [ ] Run the new test → expect red (no call site yet).
- [ ] Edit `app/agents/_base.py` `Agent.run` to invoke `validate_input` after `build_input` and short-circuit on abort. Also tighten `AgentRunFailure` to carry `reason` and `attempts` (rename `final_error`/`attempt_count` if sub-plan 1 chose different field names — pick the spec's names: `reason`, `attempts`).

  ```python
  # app/agents/_base.py — inside Agent.run, between build_input and the loop
  def run(self, ctx: Any, inputs: dict) -> OutputT | AgentRunFailure:
      """Execute the agent lifecycle and return the parsed output or a failure record."""
      self.before_run(ctx, inputs)
      user_text = self.build_input(ctx, inputs)

      input_verdict = self.validate_input(user_text)
      if input_verdict.is_abort:
          failure = AgentRunFailure(
              agent_name=self.name,
              reason=input_verdict.reason or "",
              attempts=0,
          )
          self.after_run(failure, attempts=0)
          return failure

      # ... continues into the retry loop (T3/T4)
  ```

- [ ] Re-run the test → expect green.
- [ ] Run `make test` → expect green.
- [ ] Commit: `feat(agents): wire validate_input into Agent.run`

## T3 — `validate_output` call site

- [ ] Append failing tests to `tests/unit/agents/test_lifecycle.py`.

  ```python
  class _SemanticAgent(Agent):
      """Test agent whose output gate is driven by a queue of verdicts."""

      name = "semantic_demo"
      system_prompt = "system"
      output_schema = _DemoOutput

      def __init__(self, llm: Any, verdicts: list[OutputVerdict]) -> None:
          """Store the queue of output verdicts the gate will return in order."""
          super().__init__(llm=llm)
          self._verdicts = list(verdicts)

      def build_input(self, ctx: Any, inputs: dict) -> str:
          """Return a fixed user text."""
          return "hello"

      def validate_output(self, output: _DemoOutput, ctx: Any) -> OutputVerdict:
          """Pop the next scripted verdict."""
          return self._verdicts.pop(0)


  def test_validate_output_ok_first_attempt_returns_output() -> None:
      llm = FakeLLM(canned={"_DemoOutput": {"value": "a"}})
      agent = _SemanticAgent(llm=llm, verdicts=[OutputVerdict.ok()])

      result = agent.run(ctx=None, inputs={})

      assert isinstance(result, _DemoOutput)
      assert result.value == "a"


  def test_validate_output_fail_short_circuits_without_retry() -> None:
      llm = FakeLLM(canned={"_DemoOutput": {"value": "a"}})
      agent = _SemanticAgent(llm=llm, verdicts=[OutputVerdict.fail("hard")])

      result = agent.run(ctx=None, inputs={})

      assert isinstance(result, AgentRunFailure)
      assert result.reason == "hard"
      assert result.attempts == 1
  ```

- [ ] Run → expect red.
- [ ] Extend `Agent.run` to call `validate_output` after parsing.

  ```python
  # app/agents/_base.py — inside Agent.run, post-parse branch
  parsed = self._invoke_llm(user_text)  # raises ValidationError → schema retry path
  output_verdict = self.validate_output(parsed, ctx)
  if output_verdict.is_ok:
      self.after_run(parsed, attempts=attempt)
      return parsed
  if output_verdict.is_fail:
      failure = AgentRunFailure(
          agent_name=self.name,
          reason=output_verdict.reason or "",
          attempts=attempt,
      )
      self.after_run(failure, attempts=attempt)
      return failure
  # is_retry → falls through to T4 retry loop with reason appended
  ```

- [ ] Re-run → expect green.
- [ ] `make test` → green.
- [ ] Commit: `feat(agents): wire validate_output into Agent.run`

## T4 — Unified retry loop

- [ ] Append failing tests covering shared-budget behaviour.

  ```python
  def test_retry_then_ok_returns_output() -> None:
      llm = FakeLLM(canned={"_DemoOutput": {"value": "a"}})
      verdicts = [OutputVerdict.retry("nudge"), OutputVerdict.ok()]
      agent = _SemanticAgent(llm=llm, verdicts=verdicts)

      result = agent.run(ctx=None, inputs={})

      assert isinstance(result, _DemoOutput)
      assert result.value == "a"


  def test_retry_then_retry_exhausts_and_fails() -> None:
      llm = FakeLLM(canned={"_DemoOutput": {"value": "a"}})
      verdicts = [OutputVerdict.retry("first"), OutputVerdict.retry("second")]
      agent = _SemanticAgent(llm=llm, verdicts=verdicts)

      result = agent.run(ctx=None, inputs={})

      assert isinstance(result, AgentRunFailure)
      assert result.reason == "exhausted"
      assert result.attempts == 2
  ```

- [ ] Run → expect red.
- [ ] Replace the loop body of `Agent.run` with the unified retry loop. Schema and semantic failure share `attempt`.

  ```python
  # app/agents/_base.py — full Agent.run loop body (sketch)
  attempt = 0
  user_text_current = user_text
  last_reason = ""
  while attempt <= self.retry.max_retries:
      attempt += 1
      try:
          parsed = self._invoke_llm(user_text_current)
      except ValidationError as e:
          last_reason = f"schema: {e}"
          if attempt > self.retry.max_retries:
              break
          self.on_retry(last_reason, attempt=attempt + 1)
          user_text_current = _append_retry_reason(user_text, last_reason)
          continue

      verdict = self.validate_output(parsed, ctx)
      if verdict.is_ok:
          self.after_run(parsed, attempts=attempt)
          return parsed
      if verdict.is_fail:
          failure = AgentRunFailure(
              agent_name=self.name,
              reason=verdict.reason or "",
              attempts=attempt,
          )
          self.after_run(failure, attempts=attempt)
          return failure
      # is_retry
      last_reason = verdict.reason or ""
      if attempt > self.retry.max_retries:
          break
      self.on_retry(last_reason, attempt=attempt + 1)
      user_text_current = _append_retry_reason(user_text, last_reason)

  failure = AgentRunFailure(
      agent_name=self.name,
      reason="exhausted" if last_reason else "exhausted",
      attempts=attempt,
  )
  self.after_run(failure, attempts=attempt)
  return failure
  ```

  Helper:

  ```python
  def _append_retry_reason(user_text: str, reason: str) -> str:
      """Append a retry reason block to the user prompt for the next attempt."""
      return (
          user_text
          + "\n\n# Previous attempt was rejected:\n"
          + reason
          + "\n\nRevise your answer accordingly."
      )
  ```

  `RetryPolicy` default stays `max_retries=1`. Confirm the dataclass on `Agent`:

  ```python
  retry: RetryPolicy = RetryPolicy()  # max_retries=1 → at most 2 LLM calls
  ```

- [ ] Run → expect green.
- [ ] `make test` → green.
- [ ] Commit: `feat(agents): unify schema and semantic retry budget`

## T5 — `on_retry` telemetry slot

- [ ] Append failing test asserting `on_retry` fires exactly once when there is one retry, with the reason and attempt index.

  ```python
  class _RecordingAgent(_SemanticAgent):
      """Captures on_retry invocations for assertion."""

      def __init__(self, llm: Any, verdicts: list[OutputVerdict]) -> None:
          """Initialise recorder list."""
          super().__init__(llm=llm, verdicts=verdicts)
          self.retry_calls: list[tuple[str, int]] = []

      def on_retry(self, reason: str, attempt: int) -> None:
          """Record the call instead of emitting telemetry."""
          self.retry_calls.append((reason, attempt))


  def test_on_retry_fires_once_per_retry() -> None:
      llm = FakeLLM(canned={"_DemoOutput": {"value": "a"}})
      verdicts = [OutputVerdict.retry("nudge"), OutputVerdict.ok()]
      agent = _RecordingAgent(llm=llm, verdicts=verdicts)

      agent.run(ctx=None, inputs={})

      assert agent.retry_calls == [("nudge", 2)]


  def test_on_retry_not_called_when_first_attempt_ok() -> None:
      llm = FakeLLM(canned={"_DemoOutput": {"value": "a"}})
      agent = _RecordingAgent(llm=llm, verdicts=[OutputVerdict.ok()])

      agent.run(ctx=None, inputs={})

      assert agent.retry_calls == []
  ```

- [ ] Run → expect green for the second test (no slot called yet) but red for the first (no call site).

- [ ] Add the default `on_retry` to `Agent` and confirm the loop in T4 already invokes it. Default emits span event + structured log.

  ```python
  # app/agents/_base.py
  import hashlib

  from app.core.logs import get_logger
  from app.core.tracing import get_tracer

  _log = get_logger(__name__)


  class Agent(Generic[InputT, OutputT]):
      # ... other slots from sub-plan 1 ...

      def on_retry(self, reason: str, attempt: int) -> None:
          """Emit a span event and a structured log for one retry boundary."""
          reason_hash = hashlib.sha256(reason.encode("utf-8")).hexdigest()[:12]
          span = get_tracer(__name__).start_span(f"agent.{self.name}.retry")
          try:
              span.add_event(
                  "agent.retry",
                  {"attempt": attempt, "reason_hash": reason_hash},
              )
          finally:
              span.end()
          _log.info(
              "agent.retry_reason",
              agent=self.name,
              attempt=attempt,
              reason=reason,
          )
  ```

- [ ] Re-run → expect green.
- [ ] `make test` → green.
- [ ] Commit: `feat(agents): emit on_retry span event and log`

## T6 — `before_run` / `after_run` slots

- [ ] Append failing tests asserting both slots fire exactly once per `Agent.run` invocation, success or failure.

  ```python
  class _ProbeAgent(_SemanticAgent):
      """Captures before_run / after_run invocations."""

      def __init__(self, llm: Any, verdicts: list[OutputVerdict]) -> None:
          """Initialise probe lists."""
          super().__init__(llm=llm, verdicts=verdicts)
          self.before_calls: list[tuple[Any, dict]] = []
          self.after_calls: list[tuple[Any, int]] = []

      def before_run(self, ctx: Any, inputs: dict) -> None:
          """Record entry."""
          self.before_calls.append((ctx, dict(inputs)))

      def after_run(self, result: Any, attempts: int) -> None:
          """Record exit."""
          self.after_calls.append((result, attempts))


  def test_before_and_after_fire_on_success() -> None:
      llm = FakeLLM(canned={"_DemoOutput": {"value": "a"}})
      agent = _ProbeAgent(llm=llm, verdicts=[OutputVerdict.ok()])

      result = agent.run(ctx="C", inputs={"k": 1})

      assert agent.before_calls == [("C", {"k": 1})]
      assert len(agent.after_calls) == 1
      assert agent.after_calls[0][0] is result
      assert agent.after_calls[0][1] == 1


  def test_before_and_after_fire_on_input_abort() -> None:
      class _AbortAgentProbe(_ProbeAgent):
          def validate_input(self, user_text: str) -> InputVerdict:
              """Always abort."""
              return InputVerdict.abort("nope")

      llm = FakeLLM(canned={})
      agent = _AbortAgentProbe(llm=llm, verdicts=[])

      result = agent.run(ctx="C", inputs={})

      assert agent.before_calls == [("C", {})]
      assert agent.after_calls and agent.after_calls[0][1] == 0
      assert isinstance(result, AgentRunFailure)
  ```

- [ ] Run → expect red where T2's abort path or T4's success path doesn't yet call `after_run`.
- [ ] Confirm every return path in `Agent.run` (input abort, semantic ok, semantic fail, exhausted, schema-exhausted) calls `self.after_run(...)` exactly once. The skeleton in T2/T3/T4 already shows the call sites — assert all five paths are covered.
- [ ] Default slot implementations (already added in sub-plan 1) stay as no-ops:

  ```python
  def before_run(self, ctx: Any, inputs: dict) -> None:
      """Default no-op entry hook; subclasses may override."""

  def after_run(self, result: OutputT | AgentRunFailure, attempts: int) -> None:
      """Default no-op exit hook; subclasses may override."""
  ```

- [ ] Re-run → green.
- [ ] `make test` → green.
- [ ] Commit: `feat(agents): invoke before_run and after_run on every exit path`

## T7 — Combination coverage

- [ ] Add the remaining cases to `tests/unit/agents/test_lifecycle.py` to satisfy the spec checklist.

  ```python
  def test_validate_output_ok_no_retry() -> None:
      # already covered by test_validate_output_ok_first_attempt_returns_output
      pass


  def test_schema_fail_then_semantic_fail_exhausts() -> None:
      """Schema error on attempt 1 → semantic retry verdict on attempt 2 → AgentRunFailure."""
      from pydantic import ValidationError

      class _OneBadOneGood(FakeLLM):
          """Raises ValidationError on the first call, returns a valid model on the second."""

          def __init__(self) -> None:
              super().__init__(canned={"_DemoOutput": {"value": "a"}})
              self.calls = 0

          def complete_with_schema(self, **kwargs: Any) -> Any:
              """First call fails schema parsing; second returns the canned model."""
              self.calls += 1
              if self.calls == 1:
                  raise ValidationError.from_exception_data(
                      "fake",
                      [{"type": "missing", "loc": ("value",), "input": {}}],
                  )
              return super().complete_with_schema(**kwargs)

      llm = _OneBadOneGood()
      agent = _SemanticAgent(llm=llm, verdicts=[OutputVerdict.retry("semantic-on-2nd")])

      result = agent.run(ctx=None, inputs={})

      assert isinstance(result, AgentRunFailure)
      assert result.attempts == 2
      assert llm.calls == 2
  ```

- [ ] Run → green (or fix anything T4 missed).
- [ ] Commit: `test(agents): cover schema-then-semantic exhaustion path`

## T8 — Test file reshuffle

- [ ] Open `tests/unit/test_framework_primitives.py` (from sub-plan 1).
- [ ] Leave the structural assertions that only check class shape and default no-op behaviour. Move every test that exercises `Agent.run` lifecycle behaviour into `tests/unit/agents/test_lifecycle.py` (already created in T2–T7).
- [ ] If any test names collide, prefix lifecycle tests with `test_lifecycle_` for clarity.
- [ ] `make test` → green.
- [ ] Commit: `test(agents): move lifecycle behaviour tests to dedicated file`

## T9 — `FakeLLM.script_responses` extension

- [ ] Add a failing test for the scripted-sequence behaviour.

  ```python
  # tests/fixtures/test_fake_llm.py (append)
  from __future__ import annotations

  from pydantic import BaseModel

  from tests.fixtures.fake_llm import FakeLLM


  class _Demo(BaseModel):
      value: str


  def test_script_responses_returns_each_in_order() -> None:
      llm = FakeLLM(canned={}).script_responses({"value": "first"}, {"value": "second"})

      a = llm.complete_with_schema(system="", user="", output_schema=_Demo, tool_name="t")
      b = llm.complete_with_schema(system="", user="", output_schema=_Demo, tool_name="t")

      assert a.value == "first"
      assert b.value == "second"


  def test_script_responses_raises_when_exhausted() -> None:
      import pytest

      llm = FakeLLM(canned={}).script_responses({"value": "only"})
      llm.complete_with_schema(system="", user="", output_schema=_Demo, tool_name="t")

      with pytest.raises(AssertionError, match="script exhausted"):
          llm.complete_with_schema(system="", user="", output_schema=_Demo, tool_name="t")
  ```

- [ ] Run → expect red.
- [ ] Extend `tests/fixtures/fake_llm.py`.

  ```python
  # tests/fixtures/fake_llm.py
  from __future__ import annotations

  from typing import Any


  class FakeLLM:
      """LLMProvider stub for tests; supports canned-by-schema and scripted sequences."""

      def __init__(self, canned: dict[str, dict]) -> None:
          """Initialise with optional canned responses keyed by output_schema.__name__."""
          self._canned = canned
          self._scripted: list[dict] | None = None

      def script_responses(self, *responses: dict) -> FakeLLM:
          """Configure an ordered queue of responses; one is popped per call. Chainable."""
          self._scripted = list(responses)
          return self

      def complete_with_schema(
          self,
          system: str,
          user: str,
          output_schema: type,
          tool_name: str | None = None,
          agent_name: str = "unknown",
      ) -> Any:
          """Return the next scripted response when scripted; else fall back to canned."""
          if self._scripted is not None:
              if not self._scripted:
                  raise AssertionError("FakeLLM script exhausted")
              payload = self._scripted.pop(0)
              return output_schema(**payload)

          name = output_schema.__name__
          if name not in self._canned:
              raise AssertionError(
                  f"FakeLLM has no canned response for schema {name!r}. "
                  f"Available: {sorted(self._canned)}"
              )
          return output_schema(**self._canned[name])
  ```

- [ ] Re-run → green.
- [ ] `make test` → green.
- [ ] Commit: `test(fakes): add FakeLLM.script_responses for sequenced retries`

## T10 — Principle 12

- [ ] Open `docs/PRINCIPLES.md`.
- [ ] Add a new section, numbered 12, immediately after the existing last principle.

  ```markdown
  ## 12. Agent lifecycle is a closed system

  Every LLM call goes through `Agent.run`. That method is the only place
  where schema validation and semantic validation happen, and it is the
  only place where retry-with-reason is allowed. Direct calls to a
  provider from anywhere except the `inferencing` layer are a defect.

  The lifecycle slots — `before_run`, `build_input`, `validate_input`,
  `validate_output`, `on_retry`, `after_run` — exist so that any new
  guard (PlanReviewer-style "raw LLM verdict directly into pipeline
  state" being the original anti-pattern) lands as a `validate_output`
  override rather than as ad-hoc post-processing in a calling component.

  Practically:

  - One LLM call per agent attempt; at most two attempts per `Agent.run`.
  - Schema failure and semantic failure share the retry budget.
  - Failure surfaces as `AgentRunFailure`, never as an exception, so the
    caller can choose a fallback without losing the trace.

  See also: Principle 4 (LLM as reviewer, not producer) — now enforced
  by the lifecycle, not by convention.
  ```

- [ ] `make test` → green (docs-only change still runs the suite to confirm nothing tripped).
- [ ] Commit: `docs(principles): add Principle 12 — agent lifecycle is a closed system`

---

## Done when

- All 10 tasks committed.
- `make test` green.
- `tests/unit/agents/test_lifecycle.py` exists and covers every combination listed in §7 above.
- `app/agents/_base.py` exposes `InputVerdict`, `OutputVerdict`, and the six lifecycle slots wired into `Agent.run`.
- `docs/PRINCIPLES.md` includes Principle 12.
- No code references sub-plan task names (per CLAUDE.md "Don't reference plan-task names in code").
