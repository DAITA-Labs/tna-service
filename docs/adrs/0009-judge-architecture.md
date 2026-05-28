# ADR-0009 — Judge architecture (LLM as reviewer, not producer)

**Status:** Implemented (spike) — `IdentifierFindingJudge` + `IdentifierFindingGate` live on canvas-architecture; remaining judges (identifier_phase, stage_finding, stage_phase, metadata) follow in PR 6b. Generic `judge_gate.py` follows in PR 6c.
**Builds on:** ADR-0007 (framework primitives), ADR-0008 (canvas architecture)
**Supersedes:** none

## Context

The canvas architecture (ADR-0008) puts deterministic extractors first and validators after them. Two failure modes survive that path:

1. **Ambiguous individual findings.** A `Finding` whose confidence falls below threshold, or that a structural validator flagged. The det extractor produced *something* but the surrounding signal isn't strong enough to trust it.
2. **Phase-level conflicts.** Multiple per-finding decisions disagree about the same column; cross-canonical conflicts the arbiter couldn't resolve; cardinality violations that persist after per-finding adjudication.

CLAUDE.md's load-bearing principle: **LLM as reviewer, not producer.** Det runs first; validators run; the LLM is invoked only on the residual ambiguity. The judge architecture is how that principle becomes code.

This ADR captures the learnings from the spike (`IdentifierFindingJudge` + `IdentifierFindingGate`) — what worked, what didn't, and what the rest of Tier 6 should mimic vs change.

## Decision

A judge is an `Agent` (per ADR-0007's seven primitives) wrapped by a Haystack `@component` "gate" that:

1. Filters incoming findings to those the judge should review.
2. Builds a `FindingForJudge` payload for each ambiguous finding from the surrounding context (sheet excerpt, spec snippet, alternative candidates, validator warnings, cluster context).
3. Invokes the judge once per ambiguous finding.
4. Applies the returned verdict (`keep` / `drop` / `rewrite`) to the findings list before returning.

The gate is the only thing the pipeline imports. The judge agent stays private to its gate.

### Two tiers

- **PerFindingJudge** (this spike): one LLM call per ambiguous Finding. Verdict `keep | drop | rewrite`. Cheap, parallel-friendly, scoped to single-cell decisions.
- **PhaseJudge** (PR 6b): one LLM call per phase when per-finding verdicts disagree or the arbiter couldn't resolve. Sees all phase findings + all verdicts + cross-field warnings. Output: arbitrated bag.

### Trigger rules (per-finding tier)

A finding is "ambiguous" when **either**:
- `Confidence` enum score (HIGH=1.0, MEDIUM=0.5, LOW=0.2) falls below `tuning.confidence_threshold` (default 0.7), OR
- a `ValidationWarning.affects(finding)` returns True for any warning.

Non-identifier canonicals never reach the identifier gate even if ambiguous — the prompt is identifier-specific. Each gate is responsible for the canonicals it owns.

### Verdict application semantics

| Verdict | Outcome |
|---|---|
| `keep` | Original finding flows through unchanged |
| `drop` | Finding removed; no replacement |
| `rewrite` | Finding replaced; `value_coord = verdict.alternative_coord`; `value` read live from `bundle.canvas`; `evidence += ["judge_rewrite"]`; `confidence` inherits the judge's stated verdict confidence |

`AgentRunFailure` from the judge is **fail-safe**: keep the original finding. The LLM going down must not silently delete data.

### What the judge sees, what it doesn't

The judge sees only the prebuilt `FindingForJudge`. It does **not** read the canvas, does **not** invoke any `TOOL_REGISTRY` tools, does **not** make multi-turn calls. Everything it needs to decide is rendered into the prompt body by the gate.

This is on purpose: it makes the LLM call deterministic-in-input (same `FindingForJudge` → same prompt body), cheap to replay, easy to fixture in tests.

## Consequences

### Good

**Single LLM-call boundary.** Each judge invocation is one round-trip with structured output enforced by Anthropic tool-use. Schema lives on `IdentifierVerdict`; the LLM is *forced* to emit it via `tool_choice`. Schema mismatches retry; semantic mismatches (e.g. `rewrite` without `alternative_coord`) also retry via a small `validate_*_verdict` helper.

**Pipeline never imports the judge agent.** The gate component is the only thing pipelines see. Swapping the LLM for a deterministic heuristic later is a one-file change inside the gate.

**Observability comes for free.** Every judge call emits an OTel span (`agent.identifier_finding_judge`), span events for system/user/output, token-count attrs, and structured logs (`agent.input` / `agent.response` / `agent.output` / `agent_run_success`). Replay tooling reads the logs back without modification.

**Live API call confirmed.** A spike with a real anti-pattern (extractor pulled `io_number = STY-7821` from a column whose header was `STYLE NO`) produced `decision=rewrite alternative_coord=('B', 3) confidence=high` on first attempt — ~4 seconds, ~2k input tokens, ~158 output tokens, no retries. The prompt + schema + sheet-excerpt format communicates the structural mismatch clearly.

### Bad / open

**Gate is currently sequential.** One LLM call per ambiguous finding, in order. Sheets with many ambiguous findings will block on the network. Batching is a follow-up — likely a `max_concurrent_findings` knob on the tuning that lets the gate fan out via `asyncio.gather` or a thread pool.

**Spec-snippet rendering reads the catalog directly.** `_render_spec_snippet(canonical)` calls `get_identifier_spec(canonical)`. When stage and metadata judges land (PR 6b) we'll need symmetric helpers (`get_stage_spec`, `get_metadata_spec`) or a polymorphic catalog. Not a problem today, but a refactor pressure point.

**Sheet excerpt is fixed at ±3 rows × ±3 cols.** Empirically enough for header-row anti-pattern detection. May be undersized for cross-band reasoning the stage judge will need. Treat the half-row/half-col args as tunable, not constants.

**No phase judge yet.** The spike only covers per-finding adjudication. PhaseJudge (PR 6b) needs additional plumbing: collecting all per-finding verdicts, computing disagreements, building a phase-level prompt. The signature will be different and we should not assume the spike's prompt patterns carry over verbatim.

**Verdict confidence ≠ extraction confidence.** The judge's `confidence` is its certainty about the *verdict*, not about the resulting value. We map it directly onto the Finding's `Confidence` ladder for now. If judges become systematically over-confident this needs recalibration.

### Open questions for PR 6b / 6c

- **Should phase judges receive per-finding decision_notes?** The judge's long-form reasoning is captured via `decision_notes` when `tuning.capture_decision_notes=True`. The phase judge might benefit from seeing those traces; we deferred until the phase judge is concrete.
- **How to gate the gate?** PR 6c introduces a generic `judge_gate.py`. We should be able to express "this gate runs only when det confidence is below X AND any of {warnings A, B, C} fired" declaratively. Don't bake those rules into each gate.
- **Eval impact target.** Tier 6 exit bar is +5pts identifier recall. We can only measure after PR 6c wires gates into the per-phase pipelines and runs the canvas eval against the dataset. Don't claim the +5pts before that run lands.

## Implementation notes

Files added across PR 6a.1 and 6a.2:

```
app/agents/judges/identifier_finding/
  __init__.py
  agent.py             # IdentifierFindingJudge(Agent)
  schema.py            # FindingForJudge, IdentifierVerdict
  tuning.py            # IdentifierJudgeTuning(confidence_threshold=0.7)
  validators.py        # validate_identifier_verdict — rewrite ⇒ coord set;
                       # keep/drop ⇒ coord None

app/prompts/judges/
  __init__.py
  identifier_finding.py    # IDENTIFIER_FINDING_JUDGE prompt

app/components/judges/
  __init__.py
  identifier_finding_gate.py   # IdentifierFindingGate(@component) +
                                # _apply_verdict, _render_sheet_excerpt,
                                # _render_spec_snippet
```

Wired into `app/prompts/__init__.py`. No pipeline integration yet — that happens in PR 6c when the gate gets composed into the identifier-phase pipeline alongside the existing canvas validators.

Tests cover the schema, semantic validator, build_input rendering, FakeLLM end-to-end with retry paths, and the gate's routing + verdict-application logic (54 new tests across the two PRs).

The live probe against `claude-sonnet-4-6` ran once during the spike and was deleted — its purpose was to validate the end-to-end interface, not to live in the repo.
