# Canvas Architecture — Tier 5: Validators

> Detailed task steps written immediately before tier starts. Outline only.

**Goal:** Land `app/components/validators/` — structural-query validators that read typed records (findings + structure_bag) and emit `ValidationWarning`s. These trigger judge invocation in Tier 6.

**Architecture:** See design spec §9. Validators are pure functions over typed records — no LLM, no I/O. Output is a list of `ValidationWarning` with severity (`info | warning | error`) and the findings they affect.

**Eval expectation:** validator warnings visible per finding; ambiguous findings flagged for Tier 6 judges. No recall/precision change in this tier.

**Depends on:** Tier 4 (field components emit Findings).

---

## Task overview

| PR | # | Task | Type |
|---|---|---|---|
| 5a | 1 | `app/components/validators/cardinality.py` — mandatory canonicals = PLI count | feat |
| 5a | 2 | `app/components/validators/row_alignment.py` — per-PLI-row claims align | feat |
| 5a | 3 | `app/components/validators/date_trio.py` — ≥1 of {delivery, shipment, ex_fty} per PLI | feat |
| 5b | 4 | `app/components/validators/stage_wins.py` — date identifier not inside StageArena | feat |
| 5b | 5 | `app/components/validators/merge_alignment.py` — merge consistency across columns | feat |
| 5b | 6 | `app/components/validators/quantity_dtype.py` — ≥80% int/float in [1, 100000] | feat |
| 5b | 7 | `app/components/validators/_orchestrator.py` — CanvasValidatorOrchestrator runs all | feat |

---

## Exit bar

- [ ] All 7 tasks complete; PRs 5a–5b merged
- [ ] Each validator covered by fixture tests demonstrating both pass and fail cases
- [ ] CanvasValidatorOrchestrator emits warnings in a deterministic order
- [ ] CODING_STANDARD §10 self-review on every file
- [ ] Master plan checklist updated with Tier 5 ✓

Detailed task steps to be written immediately before Tier 5 starts.
