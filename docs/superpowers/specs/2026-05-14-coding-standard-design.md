# Coding Standard + tna-service/app/ refactor — design

**Date:** 2026-05-14
**Status:** Implemented (2026-05-14)

## Problem

The `tna-service/app/` codebase has good structure and good naming overall, but its surface quality is uneven:

- **Docstring coverage is patchy.** Of 66 Python files, four modules carry zero docstrings on their functions (`telemetry.py` 0/7, `_base.py` 0/3, `plan_invariants.py` 0/3, `source_cell_verifier.py` 0/3). Many others are 1/3 or 1/10. Public functions are documented inconsistently.
- **Long, multi-purpose functions.** `configure_tracing` is 82 lines and sets up three providers, propagators, and instrumentation in one body. `_plan_for_sheet` is 77 lines. `validate_invariants` is 55 lines and runs four distinct invariant checks inline. These functions do multiple things and would be clearer as named helpers called in order.
- **No project-level coding standard.** There is no document that says "this is what a docstring looks like here", "functions should do one thing", or "this is when a helper is warranted". The patterns are in commits and headers; nothing is portable.

The user also wants a **portable standard** they can reuse across future Python repos to set the quality bar for AI agents working in the codebase.

## Goal

Produce two deliverables:

1. **`docs/CODING_STANDARD.md`** — a Python-specific, staff-engineer-grade coding standard, structured for both human readers and LLM application. Portable across repos.
2. **A fully refactored `tna-service/app/`** — 66 files, pure shape-only edits applying the standard. No behavior change. `make test` and `make eval` produce identical results before and after.

## Non-goals

- **Touching `tests/`.** Out of scope.
- **Behavior fixes.** Any real bug surfaced during refactor is logged as a follow-up commit, not folded into the refactor.
- **Architecture changes.** Layering, agent shape, validator structure, etc. stay as-is. See `ARCHITECTURE.md` for current state.
- **Lint config changes.** `pyproject.toml` ruff rules stay as-is unless they directly contradict the standard.
- **Cross-language portability.** Standard is Python-specific. A separate effort can derive language-agnostic principles later if desired.

## Design

### Two artifacts, one phased project

```
Phase 0   Draft CODING_STANDARD.md v1                                (1 commit)
           ↓
Phase P   Pilot: apply to app/services/validation/plan_invariants.py
            Subagent does the refactor + self-review.
            User reviews diff against the standard.                   (1 commit)
           ↓
Phase R   Reconcile: edit the standard if pilot revealed gaps.
            If changes are large, re-pilot.                          (0-N commits)
           ↓
       ▶ HARD GATE — user approves the final CODING_STANDARD.md ◀
           ↓
Phase 1   models/ + enums/ + schemas/                          (~10 files)
Phase 2   config/ + core/                                       (~7 files)
Phase 3   repositories/                                         (~9 files)
Phase 4   services/planner/                                     (~7 files)
Phase 5   services/agents/ + services/validation/              (~13 files)
Phase 6   services/extraction.py + reconciler + routers
            + middleware + main                                 (~12 files)
```

After every file: `make test`. At phase end: `make eval` matrix comparison + breath check before next phase. If the eval matrix shifts, the phase aborts pending investigation.

### `CODING_STANDARD.md` structure

11 sections. Each section has the same anatomy so subagents can pattern-match:

- 2–4 lines of rationale (human voice, what the rule serves)
- Imperative rules (LLM voice — "Do X. Don't Y.")
- Before/after code example (concrete from this codebase where possible)
- Section checklist (3–6 checks subagents run before declaring a file done)

| # | Section | What it covers |
|---|---|---|
| 0 | Intent / how to use this document | Purpose, application order, precedence rule when CLAUDE.md or user instruction conflicts (user instruction wins). |
| 1 | Naming | Functions, variables, classes, modules. Concise + descriptive. Verb-first for functions, noun-first for classes. Private helpers prefix `_`. No bloated names like `process_data_helper_v2`. |
| 2 | Functions | One job per function. Decomposition heuristics (the `validate_invariants` case). Soft length target with explicit override syntax. When to extract a helper. Pure functions where possible. |
| 3 | Docstrings | Required on every public function and every non-trivial private. Format: one-line summary, then `Args/Returns/Raises` only where non-obvious. Never restate the signature. |
| 4 | Comments | The "why not what" rule. Warranted when explaining a non-obvious constraint or surprising workaround. Never reference plan-task names. |
| 5 | Type hints | Mandatory on public API. Modern syntax (`int \| None`, not `Optional[int]`). Guidance on `TypeAlias`, `Protocol`, generics. |
| 6 | Error handling | Raise vs return None. Specific exception types. No bare `except`. No silent swallowing without a logged reason. Validate at boundaries, trust inside. |
| 7 | Imports | stdlib → third-party → local, alphabetised within groups. Absolute imports preferred. When lazy imports are OK (heavy optional deps, circular avoidance). |
| 8 | Module organization | One responsibility per file. Public API at the top, helpers below. When to split a file (size + cohesion signals). `__init__.py` re-export conventions. |
| 9 | Test interaction | What production code must do so tests stay clean (DI-friendly seams, no import-time global state mutation). What it must NOT do (`if TESTING:` branches, test-only kwargs). |
| 10 | Self-review checklist | One-page master checklist a subagent runs before declaring a file done. Distilled from sections 1–9. This is the artifact that drives the rollout. |

Sections 1–9 are the rules; Section 10 is the operational form. Total target: ~300 lines.

**Deliberately out:** architecture/SOLID (in `docs/PRINCIPLES.md`), specific lint config (in `pyproject.toml`), performance heuristics (too codebase-specific to be portable).

### Per-file workflow

```
1. Read CODING_STANDARD.md Section 10 checklist.
2. Read the target file end-to-end.
3. For each function:
     - Add docstring per Section 3 (if missing).
     - Decompose per Section 2 (if violating soft length / single-job rule).
     - Rename per Section 1 (if names are vague or bloated).
4. Apply Sections 4–9 as relevant.
5. Run Section 10 checklist. Fix anything that fails.
6. Run `make test`. Must pass.
7. Self-review: open `git diff` and confirm changes are ONLY shape.
     - No new conditionals.
     - No reordered statements that could change semantics.
     - No swapped exception types.
8. Commit: `refactor(<module>): apply coding standard to <file>` (single file).
9. Report back: what changed, what was left alone, any rule that felt awkward.
```

### Definition of done per file

- [ ] Every public function has a docstring matching Section 3 format.
- [ ] No function exceeds the soft length target without an explicit override marker.
- [ ] `git diff` is a pure shape change. No new behavior.
- [ ] `make test` passes.
- [ ] Naming, types, error handling, imports, module organization pass their section checklists.
- [ ] Commit message is conventional and references no plan-task names.

### Two firm rules for the rollout

1. **One file per commit, no exceptions.** Even when two files are obviously coupled. Cheap review, cheap bisect, cheap revert.
2. **No "while we're in there" fixes.** Real bugs surfaced during refactor get logged as follow-up commits, never folded in. Mixing shape with behavior in one commit is exactly how this kind of refactor goes wrong.

### Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Standard too prescriptive — fights real code | Medium | Soft length target, not hard. Pilot catches it. Subagent reports anything awkward. |
| Standard too vague — inconsistent application | Medium | Each section has imperative rules + before/after + checklist. Section 10 is the gate. |
| "Pure refactor" silently changes behavior | Low–Medium | `make test` per file, `make eval` per phase boundary, one file per commit so bisect is cheap. Subagent attests "no logic edits" in commit report. |
| Long effort stalls partway | Medium | Phases are small (10–15 files) and self-contained. Each ships green. If you pause, the codebase is consistent up to wherever we stopped. |
| `make eval` shifts mid-phase | Medium (LLM noise) vs Low (real regression) | Run twice. If both shift, real regression — bisect. If they diverge from each other, LLM non-determinism. |
| Subagent over-decomposes | Medium | Section 2 includes a "when NOT to extract" rule. Reviewer catches in diff. |
| Standard not portable to other repos | Low | First port is a stress test. We learn this after the rollout — accept the risk. |
| Scope creep — "while we're in there" fixes | High | Rule is explicit. Reviewer enforces. |

### Standard amendment policy (post-approval)

The standard is locked once approved at the Phase R gate. If a rollout phase reveals real ambiguity:

1. Subagent flags it in the commit report — does NOT amend the standard.
2. Finish the current file using the most defensible interpretation.
3. At phase end, discuss whether the standard needs an amendment.
4. Small amendment — edit, re-bless, continue. Big amendment — re-pilot before continuing.

This prevents the standard from drifting under us mid-rollout.

### Rollback granularity

- **Per-file**: `git revert <sha>`. Minutes.
- **Per-phase**: `git revert <sha1>..<shaN>`. An hour or two to redo.
- **Whole project**: `git reset --hard <pre-phase-0-sha>`. Days lost; the pilot exists to prevent this.

## Acceptance criteria

1. `docs/CODING_STANDARD.md` drafted, piloted, **approved by user (HARD GATE)** before any rollout phase starts.
2. Pilot file (`app/services/validation/plan_invariants.py`) refactored. Diff is pure-shape. `make test` passes.
3. All 6 rollout phases complete. Each phase boundary has `make eval` evidence in the commit log showing the matrix unchanged.
4. No commit in the rollout phases contains more than one source file.
5. `grep -rn "TODO\|FIXME\|XXX" app/` returns the same count after as before (no new junk while cleaning up).
6. README + ARCHITECTURE.md updated to reference `docs/CODING_STANDARD.md`.
7. This design doc's Status is flipped to `Implemented`.

## Open questions deferred to the implementation plan

- Exact soft length target for functions. The draft will pick a defensible default (likely 40–50 lines); the pilot adjusts if needed.
- Docstring format choice (Google vs NumPy vs free-form). Recommendation in the draft: one-line summary + `Args/Returns/Raises` only where non-obvious. Pilot will confirm.
- Whether to add a `make standard-check` target that runs `ruff` plus a custom checker for docstring coverage and function length. Deferred — out of v1 scope; reviewer judgement during rollout is sufficient.
- Whether the standard amendment policy should require a new ADR entry. Deferred — start with inline edits; revisit if the standard churns more than once.
