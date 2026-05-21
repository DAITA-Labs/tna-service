# ADR-0007 — Pipeline architecture redesign (seven primitives + lifecycle hooks + Haystack DSL)

**Status:** Accepted (implemented across sub-plans 1–5, 2026-05-21)
**Supersedes:** Implicit imperative orchestrator from ADR-0003

## Context

The pre-redesign codebase had three pain points: agents were doing too many
logical jobs in one LLM call, the boundaries between agents / components /
tools / inferencing were ambiguous (`@haystack.component` decorated both LLM
agents and deterministic validators), and the orchestrator's traces showed only
timing without prompts or LLM verdicts.

Additionally, `app/services/` had grown into a catch-all: `agents/`, `planner/`,
`applier/`, `validation/`, `llm_provider.py`, and `extraction.py` all lived at
the same level with no clear boundary rules. Adding a new agent or swapping a
pipeline architecture required knowing where each concern lived and touching the
orchestrator in multiple places.

## Decision

**Seven framework primitives**, each with a single clear file-system home:

| Primitive | Home | Role |
|---|---|---|
| pipeline | `app/pipelines/<name>.py` | Top-level orchestration via Haystack `Pipeline`. No business logic. |
| component | `app/components/<name>.py` | A unit the pipeline calls via `@component` + `run()`. Deterministic or LLM-backed. |
| agent | `app/agents/<name>/` | Exactly one narrow LLM mapping job. Folder: `agent.py`, `schema.py`, `tuning.py`, `validators.py`, prompt backlink. |
| tool | `app/tools/<name>.py` | Deterministic side-effect-free helper. `@tool`-decorated. |
| inferencing | `app/inferencing/<provider>.py` | Single LLM-call boundary. Owns retry, train-of-thought capture, provider SDK. |
| prompts | `app/prompts/<name>.py` | One module per prompt; one uppercase `str` constant. |
| tuning_params | `app/agents/<name>/tuning.py` + `app/pipelines/tuning.py` | `pydantic-settings` blocks per agent and per pipeline. |

**Haystack `Pipeline` as the runtime DAG.** Components are added with
`add_component()` and wired with `connect()` edges. This makes pipeline
topology inspectable, swappable, and testable in isolation. We use Haystack's
`Pipeline` DSL only — not Haystack's ReAct `Agent` class, which is loop-based
and incompatible with our induction-then-apply / O(sheets) budget invariants.

**Custom `Agent` base** (`app/agents/_base.py`) wraps a single LLM call with
lifecycle hooks: `validate_input`, `validate_output`, `before_run`, `after_run`,
`on_retry`. Hooks return typed verdicts (`InputVerdict`, `OutputVerdict`) so
semantic gates land as overrides rather than ad-hoc post-processing in callers.

**Train-of-thought observability** captures prompt + response + parsed output as
structured logs joined by `trace_id` + `span_id`. Span events carry hashes +
lengths (size-safe). Every LLM call is queryable in SigNoz by `trace_id`.

**Three-layer separation:**

```
app/routers/extract.py          — HTTP boundary (FastAPI route)
    ↓
app/services/extract_service.py — orchestration: init provider, build pipeline,
                                   prep inputs, run, unwrap response, emit metrics
    ↓
app/pipelines/extract.py        — pure DAG factories: make_per_sheet_pipeline +
                                   make_extract_pipeline
```

The service initialises the provider, builds the pipeline, prepares inputs, runs
`pipe.run(...)`, returns `reconciler.result`, and emits telemetry. The pipeline
factories are pure DAG construction: no side effects, no provider init, no metrics.

## Consequences

**Easier:**
- Adding a new agent is a folder: `agent.py` + `prompt.py` backlink +
  `schema.py` + `tuning.py` + `validators.py`. No orchestrator surgery.
- Adding a new architecture for an existing flow is a `make_<x>_pipeline()`
  factory swap; the service layer does not change.
- Every LLM call's prompt + response is queryable in SigNoz by `trace_id`.
- `app/services/` collapses to a thin orchestration layer: one file
  (`extract_service.py`).

**Constrained / unchanged:**
- `haystack-ai` becomes load-bearing — its `Pipeline` runtime, OTel tracer,
  and `@component` decorator are all in use. Swapping would require rewriting
  the factories.
- `app/services/agents/_base.py` (legacy `AgentRunner` / `AgentSpec`) and
  `app/services/llm_provider.py` are deleted. Callers that imported those must
  migrate to `app/agents/_base.py` and `app/inferencing/anthropic.py`.

## Alternatives considered

- **AgentScope, LangChain, Haystack `Agent` class** — all rejected during
  brainstorm: their ReAct + chat-style assumptions don't match our
  induction-then-apply / O(sheets) budget invariants (see Principle 11).
- **Imperative orchestrator (status quo)** — kept across sub-plans 1–5 phase F;
  replaced by Pipeline DSL in phase F-revised because swappable components /
  easy architecture experiments were an explicit goal.
- **`ConditionalRouter` for branching** — rejected in favour of self-aware
  components that early-return on missing preconditions (simpler, less
  Jinja2 noise).

## References

- Design doc: `docs/superpowers/specs/2026-05-21-pipeline-architecture-redesign-design.md`
- Implementation plans: `docs/superpowers/plans/2026-05-21-*-plan.md`
- Principles 12 (closed agent lifecycle) and 13 (auditable train of thought)
- CODING_STANDARD §11 (seven primitives + file homes)
