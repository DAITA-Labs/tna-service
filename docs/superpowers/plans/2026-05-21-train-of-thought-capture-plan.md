# Train-of-Thought Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture full prompt + response + parsed output on every LLM call, joined to the extraction's trace, so any bad mapping is reproducible without re-running.

**Architecture:** Hybrid strategy (spec §4). Span events carry metadata (hashes + lengths + counts) — safe under OTel's per-span byte limits. Structured logs carry the full text with trace_id/span_id, queryable via SigNoz Logs Explorer. Optional `decision_notes` field on agent output, off by default, asks the LLM to add a one-paragraph reasoning explanation when enabled.

**Tech Stack:** OpenTelemetry SDK 1.27+, structlog 24+, Pydantic 2.6+. SigNoz is the target backend (already wired).

---

## Conventions

- Python 3.12+, modern types (`list[X]`, `X | None`).
- `from __future__ import annotations` at top of every new file.
- One-line imperative docstrings on every public function, class, and module.
- Function bodies ≤ 40 lines (CODING_STANDARD §2). Split helpers when longer.
- No narrative comments. If the code needs a comment, refactor the names first.
- Conventional commits: `feat:`, `chore:`, `refactor:`, `test:`, `docs:`.
- `make test` runs `pytest -q -m "not live"` — must be green after every task.
- All new modules live under `app/inferencing/`, `app/agents/`, `app/core/`, `app/artifacts/` per the sub-plan-1 layout. Touch existing `app/services/agents/` only via the explicit instrumentation tasks below — no rewrites.

## Spec coverage check

| Spec §4 requirement | Covered by task |
|---|---|
| Span attrs: `agent.name`, `model`, `tokens.in`, `tokens.out`, `retries`, `status` | T2, T3 |
| Event `input.system_prompt {sha256, length}` | T1, T3 |
| Event `input.user_built {sha256, length, tools_used:[…]}` | T1, T3 |
| Event `llm.request_sent {model, max_tokens, temperature}` | T2 |
| Event `llm.response_received {duration_ms, tokens_out}` | T2 |
| Event `llm.schema_validate {ok | failed:msg}` | T1, T3 |
| Event `output.parsed_ok {schema}` | T1, T3 |
| Retry: second event pair with `attempt=2` | T3 |
| Log `agent.input` (full user prompt) | T4, T3 |
| Log `agent.response` (full LLM raw text) | T4, T2 |
| Log `agent.output` (full parsed JSON) | T4, T3 |
| Log `agent.decision_notes` when enabled | T5, T4 |
| Log `artifact.<name>` between phases | T4, T8 |
| `decision_notes: str | None` optional on agent output | T5 |
| Tuning-gated prompt directive | T5 |
| Off by default | T5 |
| Trace-id / span-id correlation on every log | T4 (reuses `add_trace_context_to_log`) |
| Test presence not text (Principle 13) | T6 |
| 4 today-agents emit new events | T7 |
| Non-LLM phase artifact snapshots (§4 last bullet) | T8 |
| Docs / SigNoz query examples | T9 |

---

## Task list

### T1 — `app/inferencing/capture.py`: event-recording helpers

- [ ] **T1.1 Write failing test** — `tests/unit/inferencing/test_capture_helpers.py`:

  ```python
  from __future__ import annotations

  from app.inferencing.capture import (
      hash_text, record_input_event, record_response_event,
      record_validate_event, record_output_event,
  )


  class _FakeSpan:
      def __init__(self) -> None:
          self.events: list[tuple[str, dict]] = []

      def add_event(self, name: str, attributes: dict) -> None:
          self.events.append((name, attributes))


  def test_hash_text_is_sha256_hex_64() -> None:
      h = hash_text("hello world")
      assert len(h) == 64
      assert all(c in "0123456789abcdef" for c in h)


  def test_record_input_event_system_prompt() -> None:
      span = _FakeSpan()
      record_input_event(span, kind="system_prompt", text="SYS")
      name, attrs = span.events[0]
      assert name == "input.system_prompt"
      assert attrs["sha256"] == hash_text("SYS")
      assert attrs["length"] == 3


  def test_record_input_event_user_built_with_tools() -> None:
      span = _FakeSpan()
      record_input_event(span, kind="user_built", text="USR",
                         tools_used=["peek_sheet", "survey"])
      name, attrs = span.events[0]
      assert name == "input.user_built"
      assert attrs["tools_used"] == ["peek_sheet", "survey"]


  def test_record_response_event_carries_duration_and_tokens() -> None:
      span = _FakeSpan()
      record_response_event(span, raw="raw", tokens_out=123, duration_ms=45.6)
      name, attrs = span.events[0]
      assert name == "llm.response_received"
      assert attrs["tokens_out"] == 123
      assert attrs["duration_ms"] == 45.6
      assert attrs["sha256"] == hash_text("raw")


  def test_record_validate_event_ok_and_failed() -> None:
      span = _FakeSpan()
      record_validate_event(span, ok=True, error=None)
      record_validate_event(span, ok=False, error="missing field val")
      assert span.events[0] == ("llm.schema_validate", {"ok": True})
      assert span.events[1] == ("llm.schema_validate",
                                {"ok": False, "error": "missing field val"})


  def test_record_output_event_schema_name() -> None:
      span = _FakeSpan()
      record_output_event(span, schema_name="CanonicalNameMap")
      assert span.events[0] == ("output.parsed_ok",
                                {"schema": "CanonicalNameMap"})
  ```

- [ ] **T1.2 Run test, see it fail** — `pytest tests/unit/inferencing/test_capture_helpers.py -q` (expect ModuleNotFoundError).

- [ ] **T1.3 Implement** — create `app/inferencing/capture.py`:

  ```python
  """Span-event helpers that record the train-of-thought capture contract."""
  from __future__ import annotations

  import hashlib
  from typing import Literal, Protocol

  InputKind = Literal["system_prompt", "user_built"]


  class _SpanLike(Protocol):
      """Minimal span surface used by capture helpers."""

      def add_event(self, name: str, attributes: dict) -> None: ...


  def hash_text(s: str) -> str:
      """Return the sha256 hex digest of the given string."""
      return hashlib.sha256(s.encode("utf-8")).hexdigest()


  def record_input_event(span: _SpanLike, *, kind: InputKind, text: str,
                         tools_used: list[str] | None = None) -> None:
      """Record an input.<kind> span event with sha256 + length (+ tools_used)."""
      attrs: dict = {"sha256": hash_text(text), "length": len(text)}
      if kind == "user_built" and tools_used is not None:
          attrs["tools_used"] = list(tools_used)
      span.add_event(f"input.{kind}", attrs)


  def record_request_event(span: _SpanLike, *, model: str, max_tokens: int,
                           temperature: float, attempt: int = 1) -> None:
      """Record an llm.request_sent event immediately before the provider call."""
      span.add_event("llm.request_sent", {
          "model": model, "max_tokens": max_tokens,
          "temperature": temperature, "attempt": attempt,
      })


  def record_response_event(span: _SpanLike, *, raw: str, tokens_out: int,
                            duration_ms: float, attempt: int = 1) -> None:
      """Record an llm.response_received event with timing + token count + sha256."""
      span.add_event("llm.response_received", {
          "sha256": hash_text(raw),
          "tokens_out": tokens_out,
          "duration_ms": duration_ms,
          "attempt": attempt,
      })


  def record_validate_event(span: _SpanLike, *, ok: bool,
                            error: str | None) -> None:
      """Record an llm.schema_validate event with ok flag and optional error string."""
      attrs: dict = {"ok": ok}
      if not ok and error is not None:
          attrs["error"] = error
      span.add_event("llm.schema_validate", attrs)


  def record_output_event(span: _SpanLike, *, schema_name: str) -> None:
      """Record an output.parsed_ok event tagged with the output schema name."""
      span.add_event("output.parsed_ok", {"schema": schema_name})


  def record_retry_event(span: _SpanLike, *, attempt: int, reason: str) -> None:
      """Record an agent.retry event when a retry is about to happen."""
      span.add_event("agent.retry", {"attempt": attempt, "reason": reason})
  ```

- [ ] **T1.4 Run test, see it pass** — `pytest tests/unit/inferencing/test_capture_helpers.py -q`.

- [ ] **T1.5 Run full suite** — `make test`. Green required.

- [ ] **T1.6 Commit** — `feat: add inferencing.capture helpers for train-of-thought span events`.

---

### T2 — wire capture into `app/inferencing/anthropic.py`

(Sub-plan 1 created this file; this task edits it. If sub-plan 1 hasn't shipped yet in the working branch, instead edit `app/services/llm_provider.py:AnthropicProvider.complete_with_schema` — the contract is identical.)

- [ ] **T2.1 Write failing test** — `tests/unit/inferencing/test_anthropic_capture.py`:

  ```python
  from __future__ import annotations

  from unittest.mock import MagicMock

  from pydantic import BaseModel

  from app.inferencing.anthropic import AnthropicProvider


  class _Out(BaseModel):
      val: int


  def _fake_resp(text: str, in_tok: int, out_tok: int):
      block = MagicMock()
      block.type = "tool_use"
      block.name = "emit_test"
      block.input = {"val": 1}
      usage = MagicMock(input_tokens=in_tok, output_tokens=out_tok)
      resp = MagicMock(content=[block], stop_reason="tool_use", usage=usage)
      resp._raw_text = text
      return resp


  def test_provider_records_request_and_response_events(monkeypatch) -> None:
      from opentelemetry import trace
      from opentelemetry.sdk.trace import TracerProvider
      from opentelemetry.sdk.trace.export import SimpleSpanProcessor
      from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
          InMemorySpanExporter,
      )

      exporter = InMemorySpanExporter()
      provider = TracerProvider()
      provider.add_span_processor(SimpleSpanProcessor(exporter))
      trace.set_tracer_provider(provider)

      client = MagicMock()
      client.messages.create.return_value = _fake_resp("RAW", 10, 7)
      p = AnthropicProvider(client=client, model="claude-sonnet-4-6",
                            max_tokens=1024, temperature=0.0)

      p.complete_with_schema(
          system="SYS", user="USR",
          output_schema=_Out, tool_name="emit_test",
          agent_name="t",
      )

      spans = exporter.get_finished_spans()
      llm_span = next(s for s in spans if s.name == "llm.complete")
      names = [e.name for e in llm_span.events]
      assert "llm.request_sent" in names
      assert "llm.response_received" in names
      attrs = dict(llm_span.attributes)
      assert attrs["llm.model"] == "claude-sonnet-4-6"
      assert attrs["llm.input_tokens"] == 10
      assert attrs["llm.output_tokens"] == 7
  ```

- [ ] **T2.2 Run test, see it fail** — `pytest tests/unit/inferencing/test_anthropic_capture.py -q`.

- [ ] **T2.3 Implement** — edit `app/inferencing/anthropic.py` (or `app/services/llm_provider.py` if sub-plan 1 not landed). Inside `complete_with_schema`, replace the existing span body with capture-helper calls:

  ```python
  from app.inferencing.capture import (
      record_request_event, record_response_event,
  )
  # ...

  def complete_with_schema(
      self, *, system: str, user: str,
      output_schema: type[T], tool_name: str,
      agent_name: str = "unknown",
      attempt: int = 1,
  ) -> tuple[T, str, int, int]:
      """Call Anthropic and return (parsed, raw_text, tokens_in, tokens_out)."""
      tool = schema_to_tool(tool_name, output_schema)
      t0 = time.monotonic()
      with get_tracer(__name__).start_as_current_span("llm.complete") as span:
          span.set_attribute("llm.model", self.model)
          span.set_attribute("llm.agent", agent_name)
          record_request_event(
              span, model=self.model, max_tokens=self.max_tokens,
              temperature=self.temperature, attempt=attempt,
          )
          resp = self._call_sdk(system=system, user=user,
                                tool=tool, tool_name=tool_name)
          duration_ms = (time.monotonic() - t0) * 1000.0
          tok_in, tok_out = self._extract_tokens(resp)
          raw = self._extract_raw_text(resp, tool_name)
          record_response_event(span, raw=raw, tokens_out=tok_out or 0,
                                duration_ms=duration_ms, attempt=attempt)
          self._record_usage_attrs(span, tok_in, tok_out, agent_name)
          parsed = self._parse_tool_response(
              resp=resp, tool_name=tool_name, output_schema=output_schema,
          )
          llm_inference_duration_seconds.record(
              duration_ms / 1000.0, {"model": self.model},
          )
          llm_calls_total.add(1, {"model": self.model, "status": "success"})
          return parsed, raw, tok_in or 0, tok_out or 0
  ```

  Add small helpers `_extract_tokens`, `_extract_raw_text`, `_record_usage_attrs` to keep the function ≤ 40 lines (CODING_STANDARD §2). Update the `LLMProvider` Protocol return type to `tuple[T, str, int, int]`.

- [ ] **T2.4 Update callsites that broke** — `tests/fixtures/fake_llm.py` returns the tuple; `app/services/agents/_base.py:_invoke_llm` unpacks it. Keep `AgentRunner` semantics unchanged for this task; T3 will then exercise the raw text + tokens.

  ```python
  # tests/fixtures/fake_llm.py
  class FakeLLM:
      def __init__(self, canned: dict[str, dict],
                   raw_text: str = "{}",
                   tokens_in: int = 0, tokens_out: int = 0) -> None:
          self._canned = canned
          self._raw = raw_text
          self._tokens_in = tokens_in
          self._tokens_out = tokens_out

      def complete_with_schema(self, *, system: str, user: str,
                                output_schema: type, tool_name: str | None = None,
                                agent_name: str = "unknown",
                                attempt: int = 1):
          name = output_schema.__name__
          if name not in self._canned:
              raise AssertionError(
                  f"FakeLLM has no canned response for schema {name!r}. "
                  f"Available: {sorted(self._canned)}"
              )
          return (output_schema(**self._canned[name]),
                  self._raw, self._tokens_in, self._tokens_out)
  ```

- [ ] **T2.5 Run tests, see them pass** — `pytest tests/unit/inferencing/test_anthropic_capture.py tests/unit/test_llm_provider.py tests/unit/test_agent_base.py -q`.

- [ ] **T2.6 Run full suite** — `make test`.

- [ ] **T2.7 Commit** — `refactor(inferencing): emit request/response span events and return raw text + tokens`.

---

### T3 — wire capture into `app/agents/_base.py` (also `app/services/agents/_base.py:AgentRunner`)

- [ ] **T3.1 Write failing test** — `tests/unit/inferencing/test_trainofthought_capture.py`:

  ```python
  from __future__ import annotations

  from opentelemetry import trace
  from opentelemetry.sdk.trace import TracerProvider
  from opentelemetry.sdk.trace.export import SimpleSpanProcessor
  from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
      InMemorySpanExporter,
  )
  from pydantic import BaseModel

  from app.services.agents._base import (
      AgentSpec, AgentRunner, RetryPolicy,
  )
  from tests.fixtures.fake_llm import FakeLLM


  class Out(BaseModel):
      val: int


  def _spec():
      return AgentSpec(
          name="dummy",
          system_prompt="SYS",
          output_schema=Out,
          build_user_input=lambda c, i: "USR",
          retry=RetryPolicy(max_retries=1),
      )


  def _exporter():
      e = InMemorySpanExporter()
      tp = TracerProvider()
      tp.add_span_processor(SimpleSpanProcessor(e))
      trace.set_tracer_provider(tp)
      return e


  def test_capture_emits_all_required_events_for_one_call():
      exporter = _exporter()
      llm = FakeLLM(canned={"Out": {"val": 1}}, raw_text="RAW", tokens_out=12)
      out = AgentRunner(_spec(), llm).run(ctx=None, inputs={})
      assert isinstance(out, Out)

      spans = exporter.get_finished_spans()
      agent_span = next(s for s in spans if s.name == "agent.dummy")
      event_names = [e.name for e in agent_span.events]
      assert "input.system_prompt" in event_names
      assert "input.user_built" in event_names
      assert "llm.schema_validate" in event_names
      assert "output.parsed_ok" in event_names

      attrs = dict(agent_span.attributes)
      assert attrs["agent.name"] == "dummy"
      assert attrs["agent.status"] == "success"
      assert attrs["retries"] == 0


  def test_capture_emits_attempt_2_events_on_retry():
      exporter = _exporter()

      class FlipLLM:
          def __init__(self):
              self.calls = 0
          def complete_with_schema(self, *, system, user, output_schema,
                                    tool_name=None, agent_name="unknown",
                                    attempt=1):
              self.calls += 1
              if self.calls == 1:
                  from pydantic import ValidationError
                  raise ValidationError.from_exception_data(
                      "Out", [{"type": "missing", "loc": ("val",), "input": {}}])
              return Out(val=99), "RAW2", 0, 5

      AgentRunner(_spec(), FlipLLM()).run(ctx=None, inputs={})
      agent_span = next(s for s in exporter.get_finished_spans()
                         if s.name == "agent.dummy")
      retries = [e for e in agent_span.events if e.name == "agent.retry"]
      assert len(retries) == 1
      assert retries[0].attributes["attempt"] == 2
      assert dict(agent_span.attributes)["retries"] == 1
  ```

- [ ] **T3.2 Run test, see it fail** — `pytest tests/unit/inferencing/test_trainofthought_capture.py -q`.

- [ ] **T3.3 Implement** — edit `app/services/agents/_base.py` (and mirror in `app/agents/_base.py` if sub-plan 1 created it). Inside `AgentRunner.run`, after opening the `agent.<name>` span:

  ```python
  from app.inferencing.capture import (
      record_input_event, record_validate_event,
      record_output_event, record_retry_event,
  )
  from app.core.log_capture import log_agent_io
  # ...

  with get_tracer(__name__).start_as_current_span(f"agent.{self.spec.name}") as span:
      span.set_attribute("agent.name", self.spec.name)
      record_input_event(span, kind="system_prompt", text=self.spec.system_prompt)
      tools_used = list(inputs.get("_tools_used", []))
      record_input_event(span, kind="user_built", text=user, tools_used=tools_used)
      log_agent_io(self.spec.name, kind="input", payload=user)

      retries = 0
      while attempt <= self.spec.retry.max_retries:
          attempt += 1
          try:
              parsed, raw, tok_in, tok_out = self._invoke_llm(
                  tool_name, user, attempt=attempt,
              )
              record_validate_event(span, ok=True, error=None)
              record_output_event(span,
                                  schema_name=self.spec.output_schema.__name__)
              log_agent_io(self.spec.name, kind="response", payload=raw)
              log_agent_io(self.spec.name, kind="output",
                            payload=parsed.model_dump())
              span.set_attribute("model", self.llm.model)
              span.set_attribute("tokens.in", tok_in)
              span.set_attribute("tokens.out", tok_out)
              span.set_attribute("retries", retries)
              self._record_attempt_success(run_t0, attempt, span)
              return parsed
          except ValidationError as e:
              last_error = str(e)
              record_validate_event(span, ok=False, error=last_error[:200])
              retries += 1
              agent_retry_count.add(1, {"agent": self.spec.name,
                                          "reason": "schema_validation"})
              if attempt > self.spec.retry.max_retries:
                  break
              record_retry_event(span, attempt=attempt + 1,
                                  reason="schema_validation")
              user = _build_retry_prompt(user, last_error)
          except Exception as e:
              # unchanged — see existing branch
              ...
      span.set_attribute("retries", retries)
      return self._record_run_failure(run_t0, attempt, last_error, span)
  ```

  Adjust `_invoke_llm` to forward `attempt` and to unpack the new tuple returned by the provider.

- [ ] **T3.4 Run test, see it pass** — `pytest tests/unit/inferencing/test_trainofthought_capture.py -q`.

- [ ] **T3.5 Run full suite** — `make test`.

- [ ] **T3.6 Commit** — `feat(agents): emit input/validate/output span events + structured logs from AgentRunner`.

---

### T4 — `app/core/log_capture.py`: structured-log helper

- [ ] **T4.1 Write failing test** — `tests/unit/test_log_capture.py`:

  ```python
  from __future__ import annotations

  import structlog
  from structlog.testing import capture_logs

  from app.core.log_capture import log_agent_io, log_artifact


  def test_log_agent_io_emits_event_with_artifact_kind_and_agent():
      with capture_logs() as caps:
          log_agent_io("field_namer", kind="input", payload="full prompt text")
      assert caps, "no event captured"
      ev = caps[0]
      assert ev["event"] == "agent.input"
      assert ev["agent"] == "field_namer"
      assert ev["artifact_kind"] == "input"
      assert ev["payload"] == "full prompt text"


  def test_log_agent_io_dict_payload_round_trips():
      with capture_logs() as caps:
          log_agent_io("plan_reviewer", kind="output",
                        payload={"verdict": "looks_correct"})
      assert caps[0]["payload"] == {"verdict": "looks_correct"}


  def test_log_artifact_emits_named_event_under_artifact_prefix():
      with capture_logs() as caps:
          log_artifact("plan.snapshot_after_planner",
                        payload={"pli_mode": "ROW_PER_PLI"})
      assert caps[0]["event"] == "artifact.plan.snapshot_after_planner"
      assert caps[0]["artifact_kind"] == "snapshot"


  def test_decision_notes_kind_uses_dedicated_event_name():
      with capture_logs() as caps:
          log_agent_io("field_namer", kind="decision_notes",
                        payload="one paragraph of reasoning")
      assert caps[0]["event"] == "agent.decision_notes"
  ```

- [ ] **T4.2 Run test, see it fail** — `pytest tests/unit/test_log_capture.py -q`.

- [ ] **T4.3 Implement** — create `app/core/log_capture.py`:

  ```python
  """Structured-log helpers for agent I/O and inter-phase artifact snapshots."""
  from __future__ import annotations

  from typing import Any, Literal

  from app.core.logs import get_logger

  IoKind = Literal["input", "response", "output", "decision_notes"]

  _log = get_logger("app.agent_io")


  def log_agent_io(agent: str, *, kind: IoKind, payload: Any) -> None:
      """Emit a structured log carrying the full agent prompt/response/output."""
      _log.info(
          f"agent.{kind}",
          agent=agent,
          artifact_kind=kind,
          payload=payload,
      )


  def log_artifact(name: str, *, payload: Any) -> None:
      """Emit a structured log carrying an inter-phase artifact snapshot."""
      _log.info(
          f"artifact.{name}",
          artifact_kind="snapshot",
          payload=payload,
      )
  ```

  Note: `add_trace_context_to_log` and `emit_to_otel_logs` in `app/core/tracing.py` are already installed as structlog processors by `configure_logging()`. They inject `trace_id` + `span_id` automatically when a span is active, so callers do not pass them explicitly.

- [ ] **T4.4 Run test, see it pass** — `pytest tests/unit/test_log_capture.py -q`.

- [ ] **T4.5 Run full suite** — `make test`.

- [ ] **T4.6 Commit** — `feat(core): add log_agent_io + log_artifact for train-of-thought log capture`.

---

### T5 — `decision_notes` mixin + tuning gate

- [ ] **T5.1 Write failing test** — `tests/unit/inferencing/test_decision_notes_optional.py`:

  ```python
  from __future__ import annotations

  from pydantic import BaseModel

  from app.artifacts.agent_io import AgentOutput, DECISION_NOTES_DIRECTIVE
  from app.inferencing.tuning import AgentTuning, render_prompt


  class CanonicalNameMapLike(AgentOutput):
      field_labels: dict[str, str] = {}


  def test_agent_output_accepts_decision_notes_when_present():
      m = CanonicalNameMapLike(field_labels={"a": "b"},
                                decision_notes="because")
      assert m.decision_notes == "because"


  def test_agent_output_decision_notes_defaults_to_none():
      m = CanonicalNameMapLike()
      assert m.decision_notes is None


  def test_render_prompt_omits_directive_when_capture_disabled():
      tuning = AgentTuning(capture_decision_notes=False)
      out = render_prompt("BASE PROMPT", tuning=tuning)
      assert DECISION_NOTES_DIRECTIVE not in out


  def test_render_prompt_appends_directive_when_capture_enabled():
      tuning = AgentTuning(capture_decision_notes=True)
      out = render_prompt("BASE PROMPT", tuning=tuning)
      assert DECISION_NOTES_DIRECTIVE in out
      assert out.startswith("BASE PROMPT")
  ```

- [ ] **T5.2 Run test, see it fail** — `pytest tests/unit/inferencing/test_decision_notes_optional.py -q`.

- [ ] **T5.3 Implement** — create `app/artifacts/agent_io.py`:

  ```python
  """Base output model carrying the optional decision_notes field."""
  from __future__ import annotations

  from pydantic import BaseModel, ConfigDict, Field


  DECISION_NOTES_DIRECTIVE = (
      "\n\n# Decision notes\n"
      "Include a `decision_notes` field with a one-paragraph explanation of "
      "the mappings you produced and why. Mention any ambiguous cases."
  )


  class AgentOutput(BaseModel):
      """Common base for agent output schemas; carries optional decision_notes."""

      model_config = ConfigDict(extra="ignore")
      decision_notes: str | None = Field(default=None)
  ```

  Create `app/inferencing/tuning.py`:

  ```python
  """Tuning model + prompt-rendering helper shared by all agents."""
  from __future__ import annotations

  from pydantic import BaseModel, Field

  from app.artifacts.agent_io import DECISION_NOTES_DIRECTIVE


  class AgentTuning(BaseModel):
      """Pipeline-shared per-agent knobs; agents extend for their own thresholds."""

      max_retries: int = 1
      capture_decision_notes: bool = False
      sample_rows: int = Field(default=8, ge=1, le=64)


  def render_prompt(base: str, *, tuning: AgentTuning) -> str:
      """Append the decision-notes directive to base when tuning enables capture."""
      if tuning.capture_decision_notes:
          return base + DECISION_NOTES_DIRECTIVE
      return base
  ```

  Update `app/models/artifacts.py:CanonicalNameMap`, `PlanVerdict`, `LayoutHints` to inherit from `AgentOutput` instead of `BaseModel`. Keep their existing fields; the only change is the optional `decision_notes` is now present. Re-run the existing `tests/unit/test_artifacts.py` to confirm nothing breaks.

- [ ] **T5.4 Run test, see it pass** — `pytest tests/unit/inferencing/test_decision_notes_optional.py tests/unit/test_artifacts.py -q`.

- [ ] **T5.5 Wire into AgentRunner** — when `AgentSpec.tuning` is present (new optional field), feed `render_prompt(spec.system_prompt, tuning=spec.tuning)` into the LLM call, and if `parsed.decision_notes` is non-None, additionally emit `log_agent_io(name, kind="decision_notes", payload=parsed.decision_notes)`:

  ```python
  # in AgentSpec dataclass:
  tuning: AgentTuning = field(default_factory=AgentTuning)

  # in AgentRunner.run, just before invoking the LLM:
  effective_system = render_prompt(self.spec.system_prompt, tuning=self.spec.tuning)
  # pass effective_system to self.llm.complete_with_schema instead of self.spec.system_prompt

  # after successful parse:
  notes = getattr(parsed, "decision_notes", None)
  if notes:
      log_agent_io(self.spec.name, kind="decision_notes", payload=notes)
  ```

- [ ] **T5.6 Write test for end-to-end decision_notes capture** — `tests/unit/inferencing/test_decision_notes_capture.py`:

  ```python
  from __future__ import annotations

  from pydantic import BaseModel
  from structlog.testing import capture_logs

  from app.inferencing.tuning import AgentTuning
  from app.services.agents._base import AgentSpec, AgentRunner, RetryPolicy
  from app.artifacts.agent_io import AgentOutput
  from tests.fixtures.fake_llm import FakeLLM


  class Out(AgentOutput):
      val: int


  def test_decision_notes_logged_when_enabled():
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


  def test_decision_notes_not_logged_when_disabled():
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
  ```

- [ ] **T5.7 Run, see it pass** — `pytest tests/unit/inferencing/test_decision_notes_capture.py -q`.

- [ ] **T5.8 Run full suite** — `make test`.

- [ ] **T5.9 Commit** — `feat(artifacts): add optional decision_notes field with tuning-gated prompt directive`.

---

### T6 — extended in-memory capture test for both events + logs

- [ ] **T6.1 Write failing test** — `tests/unit/inferencing/test_trainofthought_capture_end_to_end.py`:

  ```python
  from __future__ import annotations

  from opentelemetry import trace
  from opentelemetry.sdk.trace import TracerProvider
  from opentelemetry.sdk.trace.export import SimpleSpanProcessor
  from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
      InMemorySpanExporter,
  )
  from pydantic import BaseModel
  from structlog.testing import capture_logs

  from app.artifacts.agent_io import AgentOutput
  from app.services.agents._base import AgentSpec, AgentRunner, RetryPolicy
  from tests.fixtures.fake_llm import FakeLLM


  class Out(AgentOutput):
      val: int


  def test_one_llm_call_emits_full_event_set_and_log_set():
      exporter = InMemorySpanExporter()
      tp = TracerProvider()
      tp.add_span_processor(SimpleSpanProcessor(exporter))
      trace.set_tracer_provider(tp)

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

      events = {e.name for s in exporter.get_finished_spans() for e in s.events}
      required_events = {
          "input.system_prompt", "input.user_built",
          "llm.schema_validate", "output.parsed_ok",
      }
      assert required_events.issubset(events), events - required_events

      log_events = {c["event"] for c in caps}
      assert {"agent.input", "agent.response", "agent.output"}.issubset(log_events)
  ```

- [ ] **T6.2 Run, see it fail then pass** — once T3 + T4 + T5 are in, this passes; if it fails diagnose with `pytest -vv`.

- [ ] **T6.3 Commit** — `test(inferencing): end-to-end coverage of capture events + logs`.

---

### T7 — instrument the four current agents

The four agents in `app/services/agents/` (`field_namer.py`, `layout_hinter.py`, `plan_reviewer.py`, `sheet_classifier.py`) all build `AgentSpec` objects and run through `AgentRunner`. Capture now happens inside `AgentRunner` (T3) and `AnthropicProvider` (T2) — so no agent body needs changes. Two small touch-ups per agent:

- [ ] **T7.1 SheetClassifier** — give it an `AgentTuning()` default and confirm:

  ```python
  # app/services/agents/sheet_classifier.py
  from app.inferencing.tuning import AgentTuning

  _TUNING = AgentTuning()  # capture_decision_notes=False by default

  _SPEC = AgentSpec(
      name="sheet_classifier",
      system_prompt=SHEET_CLASSIFIER_PROMPT,
      output_schema=SheetClassifierOutput,
      build_user_input=_build_user_input,
      retry=RetryPolicy(max_retries=1),
      tuning=_TUNING,
  )
  ```

  Add `tests/unit/test_sheet_classifier_capture.py` asserting one `agent.input` log per call.

- [ ] **T7.2 LayoutHinter** — same pattern. Test: `tests/unit/test_layout_hinter_capture.py`.

- [ ] **T7.3 PlanReviewer** — same pattern. Test: `tests/unit/test_plan_reviewer_capture.py`. Because PlanReviewer is the spec's named anti-pattern target ("raw LLM verdict into pipeline state"), this test additionally asserts the parsed `PlanVerdict` is logged before any caller can mutate it:

  ```python
  def test_plan_reviewer_logs_parsed_verdict_before_apply():
      llm = FakeLLM(canned={"PlanVerdict": {"verdict": "looks_correct"}})
      with capture_logs() as caps:
          PlanReviewer(llm=llm).run(workbook_ctx=None, plan=_min_plan(), findings=[])
      out_events = [c for c in caps if c["event"] == "agent.output"]
      assert len(out_events) == 1
      assert out_events[0]["payload"]["verdict"] == "looks_correct"
  ```

- [ ] **T7.4 FieldNamer** — same pattern. Test: `tests/unit/test_field_namer_capture.py`.

- [ ] **T7.5 Run all four** — `pytest tests/unit/test_*_capture.py tests/agent -q`.

- [ ] **T7.6 Run full suite** — `make test`.

- [ ] **T7.7 Commit** — `feat(agents): attach AgentTuning to all four production agents`.

---

### T8 — non-LLM phase snapshots via `_phase()`

The orchestrator's `_phase()` helper in `app/services/extraction.py` wraps each non-LLM phase in a span. Extend it (or its caller sites) to additionally emit one `artifact.<phase>.snapshot` structured log when the phase produces a known artifact.

- [ ] **T8.1 Write failing test** — `tests/unit/test_phase_artifact_snapshot.py`:

  ```python
  from __future__ import annotations

  from structlog.testing import capture_logs

  from app.services.extraction import _snapshot_artifact


  def test_snapshot_emits_artifact_log_for_named_phase():
      with capture_logs() as caps:
          _snapshot_artifact("plan.snapshot_after_planner",
                              payload={"pli_mode": "ROW_PER_PLI"})
      assert caps[0]["event"] == "artifact.plan.snapshot_after_planner"
      assert caps[0]["payload"] == {"pli_mode": "ROW_PER_PLI"}
  ```

- [ ] **T8.2 Run, see it fail** — `pytest tests/unit/test_phase_artifact_snapshot.py -q`.

- [ ] **T8.3 Implement** — add to `app/services/extraction.py`:

  ```python
  from app.core.log_capture import log_artifact


  def _snapshot_artifact(name: str, *, payload) -> None:
      """Emit one structured log carrying a between-phase artifact snapshot."""
      log_artifact(name, payload=payload)
  ```

  And call it in three places inside the orchestrator:

  ```python
  # after _run_planner
  _snapshot_artifact("plan.snapshot_after_planner", payload=plan.model_dump())
  # after _apply_plan_review_if_needed (only when verdict changed plan)
  _snapshot_artifact("plan.snapshot_after_reviewer", payload=plan.model_dump())
  # after FieldNamer
  _snapshot_artifact("name_map.snapshot_after_namer", payload=name_map.model_dump())
  ```

- [ ] **T8.4 Run, see it pass** — `pytest tests/unit/test_phase_artifact_snapshot.py -q`.

- [ ] **T8.5 Add orchestrator-level integration test** — `tests/flow/test_artifact_snapshots_during_extract.py`: run the existing minimal-fixture extract and assert at least the three `artifact.*` events appear in `capture_logs()`. Use an existing flow fixture; no new fixtures.

- [ ] **T8.6 Run full suite** — `make test`.

- [ ] **T8.7 Commit** — `feat(extraction): snapshot plan + name_map artifacts between phases`.

---

### T9 — operator-facing docs

- [ ] **T9.1 Write `docs/observability.md`** — one short page covering:

  - Span names introduced: `agent.<name>`, `llm.complete`, `phase.<name>`.
  - Span events: `input.system_prompt`, `input.user_built`, `llm.request_sent`, `llm.response_received`, `llm.schema_validate`, `output.parsed_ok`, `agent.retry`.
  - Span attributes: `agent.name`, `model`, `tokens.in`, `tokens.out`, `retries`, `agent.status`.
  - Structured-log events: `agent.input`, `agent.response`, `agent.output`, `agent.decision_notes`, `artifact.<name>`.
  - SigNoz Logs Explorer query example:

    ```
    service.name = "tna-service" AND attributes.agent = "field_namer"
    AND attributes.artifact_kind = "output"
    ```

  - How to read a trace in SigNoz: open a trace by `trace_id`; expand the `agent.<name>` span; events sit under "Events" tab in the timeline. Same `trace_id` shows in Logs Explorer when filtering by the trace.

  - How to enable `decision_notes`: set `tuning.capture_decision_notes=True` on the agent spec for diagnostic runs; off in production.

  ```markdown
  # Observability — Train of Thought

  Every LLM call in TNA Service emits a span and a set of structured log records that, joined by `trace_id` + `span_id`, let you reproduce the agent's decision without re-running.

  ## Spans

  | Span | When |
  |---|---|
  | `extract` | one per request (root) |
  | `phase.<name>` | one per orchestrator phase |
  | `agent.<name>` | one per agent invocation |
  | `llm.complete` | one per provider call (child of agent.<name>) |

  ## Span events (agent.<name>)

  - `input.system_prompt {sha256, length}`
  - `input.user_built {sha256, length, tools_used:[…]}`
  - `llm.schema_validate {ok | failed:<error>}`
  - `output.parsed_ok {schema}`
  - `agent.retry {attempt, reason}` on retry

  ## Span events (llm.complete)

  - `llm.request_sent {model, max_tokens, temperature, attempt}`
  - `llm.response_received {sha256, duration_ms, tokens_out, attempt}`

  ## Structured logs

  - `agent.input` — full user prompt text
  - `agent.response` — full raw LLM text
  - `agent.output` — full parsed output JSON
  - `agent.decision_notes` — when `tuning.capture_decision_notes=True`
  - `artifact.<name>` — between-phase snapshots (plan, name_map, …)

  ## SigNoz queries

  Show every prompt/response pair for a single extraction:

  ```
  service.name = "tna-service" AND trace_id = "<from trace>"
  AND (event = "agent.input" OR event = "agent.response")
  ```

  Show all FieldNamer outputs across all runs in the last hour:

  ```
  service.name = "tna-service" AND attributes.agent = "field_namer"
  AND event = "agent.output"
  ```

  ## Enabling decision_notes

  In the agent's tuning module, set `capture_decision_notes=True`. The prompt gets a directive appended; the parsed output may carry a `decision_notes` paragraph; that paragraph is logged as `agent.decision_notes`. Costs ~100–300 tokens per call. Off by default.
  ```

- [ ] **T9.2 Cross-link** — update `README.md`'s "Observability" line to point to `docs/observability.md`; update `ARCHITECTURE.md` if it has an Observability section.

- [ ] **T9.3 Commit** — `docs: add observability guide for train-of-thought capture`.

---

## Exit criteria

- `make test` green (full non-live suite).
- `pytest tests/unit/inferencing -q` shows 5+ new test files passing.
- Manual smoke (operator's call, not blocking): run one extraction against a fixture file with `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`. Open the trace in SigNoz, confirm `agent.field_namer` span has the five events listed in spec §4, and the Logs Explorer filtered by that `trace_id` shows three log rows per agent call (`agent.input`, `agent.response`, `agent.output`).
- `docs/observability.md` reviewed and merged.

## Self-review — spec §4 / §9 Principle 13 coverage

- Every span attribute in spec §4 → T2 + T3.
- Every span event in spec §4 → T1 + T2 + T3.
- Retry second event pair → T3 + the `test_capture_emits_attempt_2_events_on_retry` test.
- Full prompt/response/output as structured logs → T4 + T3.
- `decision_notes` extension, off by default, tuning-gated, logs only → T5.
- Inter-phase artifact snapshots → T8.
- Tests assert presence, not text (Principle 13) → all new tests check event names + attribute keys, never literal text bodies.
- Tests assert correct trace_id linkage → satisfied by `add_trace_context_to_log` already in the structlog processor chain; T6 verifies events + logs co-emit from the same span.
