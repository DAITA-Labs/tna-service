# Observability — Train of Thought

Every LLM call in TNA Service emits a span and a set of structured log records that, joined by `trace_id` + `span_id`, let you reproduce the agent's decision without re-running.

## Spans

| Span | When |
|---|---|
| `extract` | one per request (root) |
| `phase.<name>` | one per orchestrator phase |
| `agent.<name>` | one per agent invocation |
| `llm.complete` | one per provider call (child of `agent.<name>`) |

## Span events (agent.&lt;name&gt;)

- `input.system_prompt {sha256, length}` — fired at run start
- `input.user_built {sha256, length, tools_used:[…]}` — fired after `build_user_input`
- `llm.schema_validate {ok | failed:<error>}` — fired after parse
- `output.parsed_ok {schema}` — fired on success
- `agent.retry {attempt, reason}` — fired before each retry attempt

## Span events (llm.complete)

- `llm.request_sent {model, max_tokens, temperature, attempt}` — fired before the SDK call
- `llm.response_received {sha256, duration_ms, tokens_out, attempt}` — fired after the SDK call

## Span attributes (agent.&lt;name&gt;)

- `agent.name`, `agent.status` (`success` | `failure`)
- `model` — the LLM model identifier
- `tokens.in`, `tokens.out` — counts from the provider's usage block
- `retries` — count of retries used on this run

## Structured logs

Joined to the trace by `trace_id` and `span_id` (added automatically by the structlog processor chain).

- `agent.input` — full user prompt text
- `agent.response` — full raw LLM text
- `agent.output` — full parsed output JSON (`model.model_dump()`)
- `agent.decision_notes` — when `tuning.capture_decision_notes=True`
- `artifact.<name>` — between-phase snapshots (`plan.snapshot_after_planner`, `plan.snapshot_after_reviewer`, `name_map.snapshot_after_namer`, …)

## SigNoz queries

Show every prompt/response pair for a single extraction:

```
service.name = "tna-service" AND trace_id = "<from trace>"
AND (event = "agent.input" OR event = "agent.response")
```

Show all FieldNamer outputs across the last hour:

```
service.name = "tna-service" AND attributes.agent = "field_namer"
AND event = "agent.output"
```

Find all retries by reason:

```
service.name = "tna-service" AND event = "agent.retry"
| stats count by attributes.reason
```

## Enabling decision_notes

In an agent's tuning, set `capture_decision_notes=True`:

```python
from app.inferencing.tuning import AgentTuning

_TUNING = AgentTuning(capture_decision_notes=True)
```

When enabled, the prompt receives an appended directive asking for a one-paragraph `decision_notes`; the parsed output's `decision_notes` field is logged as `agent.decision_notes`. Costs ~100–300 tokens per call. Off by default; on for diagnostic runs.

## Reading a trace

1. Open SigNoz, navigate to **Traces**.
2. Filter by `service.name = "tna-service"` and any of: `trace_id`, `request_id`, file name, agent name.
3. Click a trace; the timeline shows `extract` → `phase.*` → `agent.*` → `llm.complete` nesting.
4. Click an `agent.<name>` span; the **Events** tab lists the 5 capture events with their attributes.
5. For the full prompt + response text, switch to **Logs Explorer** and filter by the same `trace_id` — three log rows per agent call (`agent.input`, `agent.response`, `agent.output`).

## Disabling capture

The structured logs are unconditional today. If log volume becomes a concern:
- Drop the `agent.input` / `agent.response` / `agent.output` events at the SigNoz collector via a `filter` processor in `deploy/common/otel-collector/config.yaml`.
- Or remove the relevant `log_agent_io` calls in `app/services/agents/_base.py:AgentRunner` and `app/agents/_base.py:Agent`.

(Span events on `agent.<name>` are cheap by design — sha256 + length, no full text — and stay regardless.)
