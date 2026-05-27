# Canvas Architecture — Tier 6: Judges (LLM as reviewer)

> Detailed task steps written immediately before tier starts. Outline only.

**Goal:** Land the two-tier LLM judge architecture. Per CLAUDE.md: LLM as reviewer, not producer. Det runs first; validators run; judges fire only on ambiguous findings (low confidence OR validator warning) or unresolved cross-canonical conflicts.

**Architecture:** See design spec §10. `PerFindingJudge` (one Agent invocation per ambiguous Finding) emits `Verdict { keep | drop | rewrite }`. `PhaseJudge` runs only when PerFinding cannot resolve. Each judge is an `Agent` under `app/agents/judges/`. Pipelines invoke `JudgeGateComponent`, never agents directly. The spike PR (6a) wires one judge end-to-end + ADR-0009 captures the interface learning.

**Eval expectation by end of Tier 6:** identifier recall +5pts from judge arbitration on ambiguous canonicals (especially `shipment_date`, `color_name`, MAIN FALL multi-sheet).

**Depends on:** Tiers 4 + 5 (findings + warnings available).

---

## Task overview

| PR | # | Task | Type |
|---|---|---|---|
| 6a (spike) | 1 | `app/agents/judges/identifier_finding/` — one judge end-to-end (agent.py, schema.py, tuning.py, validators.py) | feat |
| 6a (spike) | 2 | `app/prompts/judges/identifier_finding.py` — prompt constant | feat |
| 6a (spike) | 3 | `app/components/judges/identifier_finding_gate.py` — wrapper component | feat |
| 6a (spike) | 4 | `docs/adrs/0009-judge-architecture.md` — interface learnings from spike | docs |
| 6b | 5 | `app/agents/judges/identifier_phase/` — phase-level judge for identifiers | feat |
| 6b | 6 | `app/agents/judges/stage_finding/` + `stage_phase/` | feat |
| 6b | 7 | `app/agents/judges/metadata/` | feat |
| 6c | 8 | `app/components/judges/judge_gate.py` — generic gating (confidence + validator triggers) | feat |
| 6c | 9 | Wire judge gates into per-phase pipelines | feat |

---

## Cost-control tuning knobs

Per `app/agents/judges/<name>/tuning.py`:
- `confidence_threshold` (default 0.7) — invoke judge when finding confidence < threshold
- `max_concurrent_findings` — batch size for fan-out
- `decision_notes_enabled` — capture full reasoning for observability

## Exit bar

- [ ] All 9 tasks complete; PRs 6a–6c merged
- [ ] ADR-0009 captures the spike's learnings on prompt patterns, schema shape, eval impact
- [ ] FakeLLM `script_responses` covers all judges so tests don't hit the real API
- [ ] Real-LLM eval run (gated behind env var) confirms +5pts identifier recall
- [ ] Pipelines do NOT import any judge agent directly — only through `JudgeGateComponent`
- [ ] CODING_STANDARD §10 self-review on every file
- [ ] Master plan checklist updated with Tier 6 ✓

Detailed task steps to be written immediately before Tier 6 starts.
