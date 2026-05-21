# Pipeline Architecture Redesign

**Status:** Draft for review
**Date:** 2026-05-21
**Scope:** Foundational refactor of TNA Service's agent / component / tool boundaries, the observability layer, and the per-agent lifecycle. Five sub-plans, each producing its own implementable plan and PR sequence.

---

## 1. Goal

Replace today's ambiguous mix of "Haystack-decorated agents that all do too much", "scattered tools and validators", and "spans that show timing but no reasoning" with **seven named primitives** that each have a single clear role, a known home in the file tree, and instrumentation built into the base class.

The current codebase passes its tests and its eval matrix improved sharply through Feature H. What it does not do is invite a new developer to navigate it. This redesign is about that — making the next change easy to find a home for, and making any LLM-driven decision auditable end-to-end without re-running.

## 2. The four pain points this addresses

1. **Agent prompts carry too many logical tasks** — FieldNamer's current prompt encodes five distinct mapping jobs (PLI fields, metadata-bound canonicals, stage names, sub-field labels, disambiguation rules). One LLM call doing five jobs is harder to tune and harder to evaluate per-job than five focused calls would be.
2. **Pipeline boundaries are ambiguous** — `@component` decorates both LLM agents and deterministic verifiers; "tools" live in `repositories/workbook_tools/`; "agents" live in `services/agents/`; "components" is overloaded. A reader cannot answer "what kind of thing is this" from a file path.
3. **Observability lacks train of thought** — spans show that `agent.field_namer` took 4.7 seconds but never carry the prompt, the response, or the parsed verdict. Debugging a bad mapping means re-running, not reading.
4. **Code is deeper than it needs to be** — invoking an agent travels through five layers (`extraction.py` → component wrapper → `AgentRunner` → `_invoke_llm` → provider). When the substrate is rebuilt with the right primitives, that depth collapses.

## 3. The seven primitives

```
pipeline                       app/pipelines/extract.py
  └─ component (det)           app/components/<name>.py
  └─ component (LLM-backed)    app/components/<name>.py
       └─ agent                app/agents/<name>/
            ├─ agent.py
            ├─ schema.py
            ├─ tuning.py
            ├─ validators.py
            └─ inferencing ─→  app/inferencing/<provider>.py
  └─ tool (det helper)         app/tools/<name>.py

(prompts live separately, importable everywhere)
                               app/prompts/<name>.py
```

| # | Primitive | Role | Lives at |
|---|---|---|---|
| 1 | **pipeline** | Top-level orchestration of phases for one workbook. Composes components + tools. A Haystack `Pipeline` with `pipeline.connect()` edges. No business logic. No direct LLM calls. | `app/pipelines/extract.py` |
| 2 | **component** | A unit the pipeline calls. Two flavours: deterministic (e.g. `apply_plan`, validators) or LLM-backed (wraps an agent). Single `run()` entry, schema-typed inputs/outputs, Haystack `@component` decorator on top of our base. | `app/components/<name>.py` |
| 3 | **agent** | Exactly one narrow LLM mapping job per agent. FieldNamer's current 5-jobs-in-one is the anti-pattern. Co-located folder with wiring, schema, tuning, validators. | `app/agents/<name>/` |
| 4 | **tool** | Deterministic side-effect-free helper over a data source. `@tool`-decorated. Called by pipelines, components, and agent `build_input` functions — **never** invoked by the LLM. | `app/tools/<name>.py` |
| 5 | **inferencing** | The single place that talks to Anthropic / OpenAI / future providers. Surface: `(system, user, schema) → BaseModel`. Owns retry-with-error-context, train-of-thought capture, telemetry. | `app/inferencing/<provider>.py` + `_base.py` |
| 6 | **prompts** | Python module per prompt — `app/prompts/<name>.py` exports a single module-level string constant (`FIELD_NAMER`, `PLAN_REVIEWER`, `LABEL_FINDER`, …). Importable as `from app.prompts import FIELD_NAMER` or `app.prompts.LABEL_FINDER`. Includes a `_shared.py` for the SHARED header. | `app/prompts/<name>.py` |
| 7 | **tuning_params** | `pydantic-settings` block per agent (retry count, semantic + anti-pattern examples, gate thresholds, sample-row count). Plus a pipeline-level `PipelineTuning` for cross-agent knobs. | `app/agents/<name>/tuning.py` + `app/pipelines/tuning.py` |

### Why AgentScope / LangChain / Haystack `Agent` are not adopted

- **AgentScope**: ReAct + MsgHub + Trinity-RFT is a different shape of system. Adopting it would invalidate ADR-0003 (induction-then-apply), D3 (apply_plan zero-LLM), and Principle 11 (O(sheets) budget).
- **LangChain**: zero current usage; LLM adapters / output parsers / callbacks duplicate what we already own. Not added.
- **Haystack `Agent` class**: a ReAct-style loop (`max_agent_steps=100` default) returning free text. Our agents are single-call, schema-validated, with lifecycle hooks. Wrong shape.
- **Haystack `Pipeline` + `OpenTelemetryTracer` + `@component`**: ✅ adopted. The runtime gives us auto per-component spans + I/O attributes when content tracing is enabled. We layer our own LLM-side capture below the component boundary.

If a future use case calls for a LangChain Tool / Haystack Component / external LLM adapter, a **bridge adapter** wraps it at the framework boundary (`app/tools/_bridges.py`) without leaking the external shape into the pipeline. Bridges are added on demand, not pre-emptively.

## 4. Train-of-thought observability

The strategy is **hybrid** — span events for metadata, structured logs for full text. Both joined by `trace_id` + `span_id` in SigNoz.

### Per LLM-call capture contract

```
On the span (agent.<name>):
  attributes:
    agent.name, model, tokens.in, tokens.out, retries, status
  events:
    input.system_prompt     {sha256, length}
    input.user_built        {sha256, length, tools_used:[peek_sheet, …]}
    llm.request_sent        {model, max_tokens, temperature}
    llm.response_received   {duration_ms, tokens_out}
    llm.schema_validate     {ok | failed:<ValidationError>}
    output.parsed_ok        {schema:CanonicalNameMap}
  on retry: a second pair of events with attempt=2

As structured logs (joined by trace_id + span_id):
  agent.input          full user prompt text
  agent.response       full LLM raw text
  agent.output         full parsed output JSON
  agent.decision_notes (when enabled — see below)
  artifact.<name>      e.g. plan.snapshot_after_planner = SheetPlan dump
```

### `decision_notes` extension

Each agent's output schema gains an optional `decision_notes: str | None` field. When the agent's tuning has `capture_decision_notes=True`, the prompt asks for a one-paragraph explanation of the agent's mappings. Captured to logs only; costs ~100–300 tokens per call. Off by default; on for diagnostic runs. Pays off more once Feature B narrows each agent's scope (smaller decisions → more useful notes per decision).

### What Haystack tracing contributes vs what we add

Haystack's `OpenTelemetryTracer` auto-emits one span per component, with input/output dicts as attributes when `HAYSTACK_CONTENT_TRACING_ENABLED=true`. That covers the component-boundary level (artifact snapshots between phases). Everything below — the LLM call's prompt, response, retries, gate verdicts — Haystack does not see; that capture is ours, added in the inferencing layer and the Agent base class.

## 5. Per-agent lifecycle

Today's `AgentRunner` has one validation point (Pydantic schema). The new Agent base class adds two more: **`validate_input`** (catches malformed prompts before spending a call) and **`validate_output`** (semantic gate — the load-bearing addition for the "blindly accepting agent verdicts" concern).

### Lifecycle slots (new vs old)

```
Today:                          Proposed:
  build_user_input                before_run(ctx, inputs)
  loop:                           build_input(ctx, inputs) → user_text
    llm.complete_with_schema      validate_input(user_text) → ok | abort
    on ValidationError → retry    loop:
  return parsed | failure           on_request(prompt, hashes)     [telemetry]
                                    inferencing.complete(...)
                                    on_response(raw, tokens)       [telemetry]
                                    parse(raw) → model
                                    on SchemaError → retry w/ context
                                    validate_output(model, ctx)
                                    on SemanticError → retry w/ reason
                                  after_run(result, attempts)
                                  return validated | AgentRunFailure
```

### Retry policy

- Schema failure → retry once with error context appended (today's behaviour, unchanged)
- Semantic failure (`validate_output` returned not-ok) → retry once with reason appended
- After retry exhaustion → return `AgentRunFailure`; the calling component picks a fallback (e.g. empty `CanonicalNameMap`) and emits a `Warning` on the result

This bounds the per-agent LLM budget to **max two calls** — preserving Principle 11 (O(sheets) budget).

### Two tiers of validation

| Tier | Where | What |
|---|---|---|
| **Per-agent lifecycle gate** | inside `Agent.run` | `validate_input` + `validate_output`. Each agent owns these. Example: PlanReviewer's `validate_output` confirms every `row_corrections[].row` index actually exists in `plan.rows` *before* the corrections leak out of the agent. |
| **Pipeline-level validators** | between/after components | A flavour of `component`. Today's `validate_invariants`, `validate_statistics`, and the four extraction verifiers are early instances. The new ones added under `app/components/validators/` (e.g. `post_review_plan.py`, `post_namer_canonical.py`, `pre_apply_readiness.py`) close the multi-point-failure gap by re-validating after each LLM-driven mutation to plan/name_map. |

## 6. File layout — target vs today

### Top-level

```
Today                                  Proposed
─────                                  ────────
app/                                   app/
├─ services/                           ├─ pipelines/         ← orchestration
│   ├─ agents/                         │   ├─ extract.py
│   ├─ planner/                        │   └─ tuning.py
│   ├─ applier/                        ├─ components/        ← det steps
│   ├─ validation/                     │   ├─ _base.py
│   ├─ extraction.py                   │   ├─ planner/
│   ├─ llm_provider.py                 │   ├─ applier.py
│   └─ reconciler.py                   │   ├─ reconciler.py
├─ prompts/workflow/                   │   └─ validators/    ← pipeline-level
├─ repositories/                       ├─ agents/            ← one folder each
│   └─ workbook_tools/                 │   ├─ _base.py
├─ models/                             │   ├─ sheet_classifier/
├─ enums/                              │   ├─ layout_hinter/
├─ core/                               │   ├─ plan_reviewer/
├─ config/                             │   └─ field_namer/
└─ routers/                            ├─ inferencing/       ← only LLM-call site
                                       │   ├─ _base.py
                                       │   └─ anthropic.py
                                       ├─ tools/             ← flat, @tool
                                       │   ├─ _registry.py
                                       │   ├─ _decorator.py
                                       │   └─ <name>.py × N
                                       ├─ prompts/           ← module per prompt
                                       │   ├─ __init__.py
                                       │   ├─ _shared.py
                                       │   ├─ field_namer.py
                                       │   ├─ plan_reviewer.py
                                       │   ├─ layout_hinter.py
                                       │   └─ sheet_classifier.py
                                       ├─ artifacts/         ← bridge models
                                       ├─ models/            ← domain models
                                       ├─ enums/
                                       ├─ core/
                                       ├─ config/
                                       ├─ repositories/      ← workbook_repo only
                                       └─ routers/
```

### Inside one agent folder

```
app/agents/field_namer/
├─ __init__.py        re-exports FieldNamerAgent
├─ agent.py           Agent[FieldNamerInputs, CanonicalNameMap] subclass
├─ schema.py          input + output Pydantic models, incl. decision_notes
├─ tuning.py          FieldNamerTuning: retries, examples, thresholds
├─ validators.py      validate_input + validate_output
└─ tests/             agent-tier tests
```

### File-by-file migration mapping

```
app/services/extraction.py            → app/pipelines/extract.py
app/services/agents/_base.py          → app/agents/_base.py            + lifecycle hooks
app/services/agents/<name>.py         → app/agents/<name>/agent.py     wiring only
app/prompts/workflow/<name>.md        → app/prompts/<name>.py          string constant
app/prompts/_shared.md                → app/prompts/_shared.py

app/services/llm_provider.py          → app/inferencing/anthropic.py   + app/inferencing/_base.py

app/services/planner/*.py             → app/components/planner/*.py
app/services/applier/apply_plan.py    → app/components/applier.py
app/services/validation/*.py          → app/components/validators/*.py
app/services/reconciler.py            → app/components/reconciler.py

app/repositories/workbook_tools/      → app/tools/
app/models/artifacts.py               → app/artifacts/ (split per artifact group)

app/models/extraction.py              → unchanged
app/models/workbook.py                → unchanged
app/core/{logs,tracing,middleware}.py → unchanged
app/config/                           → unchanged
app/routers/                          → unchanged
```

## 7. Error handling

Three classes of failure, three propagation rules.

| Failure | Surfaces in | Behaviour |
|---|---|---|
| **Tool error** (e.g. `peek_sheet` raises) | inside an agent's `build_input` or a component | Tool emits `tool_errors_total` metric; raises typed error; calling component fallback-to-default or re-raise as component failure. |
| **Agent gate failure** (schema or semantic) | inside Agent base's lifecycle loop | First failure → append reason, retry. Second failure → return `AgentRunFailure`. Wrapping component picks fallback + emits `Warning`. |
| **Pipeline validator finding** | a component under `app/components/validators/` | Findings attached to `ExtractionResult.warnings`. Errors trigger re-plan (existing pattern); warnings just attach. |

**Invariant:** an agent failure NEVER blocks the pipeline. The pipeline always reaches `apply_plan` with some plan (possibly with a fallback `CanonicalNameMap`); `apply_plan` is zero-LLM and cannot fail for LLM reasons.

**Pipeline-wide:** uncaught exceptions get captured by the root `extract` span; `extractions_total{status="failure"}` increments; FastAPI returns 5xx.

## 8. Testing strategy

The five-tier ladder (`unit / flow / agent / e2e / live`) stays. New seams the refactor introduces:

- `tests/unit/agents/<name>/test_validators.py` — exercises `validate_input` and `validate_output` in isolation (no LLM). New surface per agent.
- `tests/unit/components/test_<name>.py` — exercises components via `Component.run()`. Includes assertions on Haystack's span attribute capture (in-memory OTel exporter).
- `tests/unit/inferencing/test_trainofthought_capture.py` — verifies prompt + response emit as structured log records with correct `trace_id` / `span_id` / `agent` keys.
- `tests/integration/test_haystack_pipeline_wiring.py` — asserts `make_extract_pipeline()` connects components in the right topology (replaces hand-checking the imperative orchestrator).
- Agent-tier tests stay the same shape (FakeLLM-backed). They now also assert the gate behaviour: semantic-fail → retry-with-reason → eventual fallback.

**`FakeLLM` extension:** `script_responses(*responses)` so agent tests can drive a sequence (first response fails semantic gate, second response passes).

## 9. Updates to PRINCIPLES and CODING_STANDARD

### New principles

- **Principle 12 — Agent lifecycle is a closed system.** Every LLM call goes through `Agent.run`, which is the only place schema + semantic validation happens. Direct provider calls from anywhere except the `inferencing` layer are a defect. PlanReviewer-style "raw LLM verdict directly into pipeline state" is the anti-pattern the lifecycle hooks exist to prevent.
- **Principle 13 — Train of thought is auditable, not optional.** Every LLM call produces (a) span events with hashes + sizes, and (b) structured log records with full prompt + response + parsed output, joined by `trace_id`. Tests assert presence, not specific text. `decision_notes` is the tuning-gated extension to add reasoning capture.

### CODING_STANDARD additions

- **§11 — Framework primitives.** Lists the seven (pipeline / component / agent / tool / inferencing / prompts / tuning_params) with one-line definitions and the "one folder per agent" rule.
- **§10 checklist additions** — per agent: validator file present, prompt module ≤ ~300 lines, tuning class declared.

### Existing principles touched

- **Principle 4 (LLM as reviewer)** — add cross-ref: now enforced by Agent base class lifecycle, not just convention.
- **Principle 11 (O(sheets) budget)** — note: `decision_notes` adds ~100–300 tokens per call but doesn't change call count.

### New ADR

**ADR-0007 — Pipeline architecture redesign.** Records the move to Haystack Pipeline + tracer adoption, custom Agent base with lifecycle hooks, and the seven-primitive layout.

## 10. Implementation — five sub-plans

Each sub-plan becomes its own implementation plan under `docs/superpowers/plans/2026-05-21-…-plan.md`. Each ships as a rollup PR to master.

### Sub-plan 1 — Framework primitives

Add the new directories (`app/pipelines/`, `app/components/`, `app/agents/`, `app/inferencing/`, `app/tools/`, `app/prompts/`, `app/artifacts/`) and the base classes (`Pipeline` factory helper, `Component` base, `Agent` base, `Provider` protocol, `@tool` decorator, `Tuning` base). No existing code moves yet — old paths still serve the API.

**Exit criterion:** `make test` green; new framework importable but unused.

### Sub-plan 2 — Train-of-thought capture

Add prompt/response capture + `decision_notes` plumbing to the `inferencing` layer. Extend `AgentRunner` (or its replacement in the Agent base) to emit the new span events + structured logs. Wire into today's four agents as instrumentation only — no rewrite.

**Exit criterion:** SigNoz Logs Explorer filtered by `trace_id` shows full prompt + response for every LLM call; new span events visible in trace waterfall.

### Sub-plan 3 — Per-agent lifecycle hooks

Extend the Agent base to call `validate_input` / `validate_output` / `on_retry`. Defaults are no-ops (back-compat). Semantic-fail retry follows the same retry-with-reason pattern as schema-fail.

**Exit criterion:** lifecycle hooks fire in order; default no-op validators preserve current behaviour; new unit tests cover the gate flow.

### Sub-plan 4 — Migrate the 4 agents (one PR per agent)

Order: `SheetClassifier` → `LayoutHinter` → `PlanReviewer` → `FieldNamer` (simplest first; most-risk last). Per agent:

1. Create `app/agents/<name>/` folder structure
2. Move prompt to `app/prompts/<name>.py` as a module-level string constant
3. Write `validate_output` (and `validate_input` where useful)
4. Define `tuning.py` with current thresholds + semantic + anti-pattern examples
5. Delete the old file
6. Update imports across the codebase

**Exit criterion per agent:** eval matrix unchanged or improved; new agent-tier tests cover gate behaviour.

### Sub-plan 5 — Migrate tools, planner, validators, applier, reconciler, and the orchestrator itself

Mostly mechanical moves + import rewrites. Tools move to `app/tools/` with a clean `@tool` decorator surface. Planner sub-components move to `app/components/planner/`. Validators (today's `app/services/validation/`) move to `app/components/validators/`, with new ones added per section 5 of this design. `app/services/applier/apply_plan.py` becomes `app/components/applier.py`. `app/services/reconciler.py` becomes `app/components/reconciler.py`.

The last step converts the orchestrator from imperative Python (`app/services/extraction.py`) to a Haystack `Pipeline` factory (`app/pipelines/extract.py`). The router (`app/routers/extract.py`) is updated to call the new pipeline factory; the orchestrator-level OTel span (`extract`) is preserved so existing trace queries keep working.

Once that lands, `app/services/` no longer exists.

**Exit criterion:** `app/services/` no longer exists; full eval green; principle/standard updates landed; Haystack content-tracing visibly emits per-component spans + I/O attributes in SigNoz; new ADR-0007 merged.

---

## 11. Out of scope

- **Eval framework refactor (Feature I — deferred).** The current eval module imports only `app/models/*` and `evals/interface.py`. It is unaffected by this redesign.
- **Confidence calibration (Feature C — deferred).** The thresholds (0.85 plan, 0.80 coverage, 0.50 dropout) move into tuning files but their values are not re-derived here.
- **Adding any new agent.** This is a substrate redesign. Adding a `LabelFinder` agent or similar lands cleanly on the new substrate but is a separate plan.
- **Migrating off Anthropic.** The `inferencing` layer's `Provider` protocol leaves room for additional providers; adding one is a separate plan.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Haystack Pipeline DSL is less readable than the imperative orchestrator | Keep the Pipeline factory function small and named (`make_extract_pipeline()`); add a docstring listing the topology |
| Per-agent folder layout multiplies file count | The increase is N agents × 5 files (~20 files for our 4 agents). The benefit — one place per concern — pays off after the second migration. |
| Migration touches almost every file | Sub-plans are mechanical and reversible. Each sub-plan ships independently; rollback is one revert per sub-plan. |
| Sub-plan 4's agent migrations could regress the eval | Run `make eval-smoke` between PRs; full `make eval` before each sub-plan's rollup. |
| Train-of-thought log volume could explode for wide sheets | `decision_notes` is opt-in. Span events carry hashes, not text. Full text goes to structured logs which SigNoz can drop by sampling if needed. |

## 13. Open questions

None at design close. All decisions during the brainstorm session captured above.
