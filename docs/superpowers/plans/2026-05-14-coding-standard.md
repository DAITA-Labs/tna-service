# Coding Standard + tna-service/app/ refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a portable `docs/CODING_STANDARD.md` and apply it to all 50 non-trivial source files in `tna-service/app/` as a pure shape-only refactor.

**Architecture:** Two artifacts, one phased project. Phase 0 drafts the standard. Phase P pilots it on one file. Phase R reconciles any standard changes from pilot. A **hard gate** requires user approval of the final standard before any rollout begins. Phases 1–6 apply the standard file-by-file across the codebase (one file per commit, `make test` per file, `make eval` per phase boundary). No behavior changes; real bugs surfaced during refactor become follow-up commits, never folded in.

**Tech Stack:** Python 3.12, pytest, ruff, `make` targets (`test`, `eval`, `lint`, `fmt`), existing CODING_STANDARD.md once drafted. Spec: `docs/superpowers/specs/2026-05-14-coding-standard-design.md`.

---

## Shared workflow — applied to every rollout task (Tasks 4+)

Every rollout task (Phases 1–6) follows this six-step procedure. Each task body lists the target file and any file-specific notes; the procedure itself is identical and is not repeated per task.

1. **Read the file end-to-end** and compare against the master checklist in `docs/CODING_STANDARD.md` Section 10.
2. **Apply shape edits**: docstrings (Section 3), function decomposition (Section 2), renaming (Section 1), then Sections 4–9 as relevant (comments, type hints, error handling, imports, module org, test-interaction).
3. **Run the Section 10 checklist** against the file. Fix any failures.
4. **Run `make test`**. Must pass. If it fails, the refactor isn't pure-shape — revert or fix.
5. **Self-review the diff** (`git diff <file>`) and confirm:
   - No new conditionals.
   - No reordered statements that could change semantics.
   - No swapped exception types.
   - No new behavior of any kind.
6. **Commit one file**: `git add <file> && git commit -m "refactor(<module>): apply coding standard to <filename>"`.

**Definition of done per file:**

- [ ] Every public function has a docstring matching Section 3 format.
- [ ] No function exceeds the soft length target without an explicit override marker.
- [ ] `git diff` is a pure shape change. No new behavior.
- [ ] `make test` passes.
- [ ] Naming, types, error handling, imports, module organization pass their section checklists.
- [ ] Commit message is conventional and references no plan-task names.

**Two firm rules for the rollout:**

1. One file per commit, no exceptions.
2. No "while we're in there" fixes. Surface real bugs as follow-up commits.

---

## Task 1: Phase 0 — Draft `docs/CODING_STANDARD.md`

**Files:**
- Create: `docs/CODING_STANDARD.md` (~300 lines, 11 sections)

The standard is the load-bearing artifact for the entire rollout. Take time on this.

- [ ] **Step 0: Capture the pre-refactor eval baseline**

Before drafting anything, capture the current `make eval` output so every phase-end verification has something to diff against.

```bash
make eval > evals/runs/baseline-pre-refactor.txt 2>&1
```

This is the file that `phase1-after.txt` through `phase6-after.txt` will be compared against. Do not commit this file (it lives under `evals/runs/` which is already in `.gitignore`).

- [ ] **Step 1: Read the spec for context**

Read `docs/superpowers/specs/2026-05-14-coding-standard-design.md` end-to-end. Note the 11 sections, the per-section anatomy (rationale → rules → before/after → checklist), the audience (mixed human + LLM), the language (Python-specific), and the scope (staff-engineer code-quality bar excluding architecture, lint config, performance).

- [ ] **Step 2: Sample the codebase for representative before/after examples**

Read at minimum:
- `app/services/validation/plan_invariants.py` (55-line `validate_invariants` — function decomposition example)
- `app/core/tracing.py` (82-line `configure_tracing` — function decomposition example)
- `app/services/applier/apply_plan.py` (10 functions, 1 docstring — docstring coverage example)
- `app/services/agents/sheet_classifier.py` (clean module — positive example)
- `app/repositories/workbook_tools/targeted.py` (3/3 docstrings — positive example)

Pull at least three real before/after pairs from these files for the standard's example slots. Real codebase examples beat generic ones.

- [ ] **Step 3: Write Section 0 — Intent / how to use this document**

Cover:
- One-paragraph purpose: this is the coding bar for any AI agent or human writing Python in this repo, and a reusable artifact for other repos.
- How to apply: subagents run Section 10 checklist per file; reviewers spot-check against Sections 1–9.
- Precedence rule: when this document conflicts with a user instruction or with `CLAUDE.md`, the user / CLAUDE.md wins.
- Amendment policy: the standard is locked once approved; rollout subagents flag ambiguities in commit reports and never amend the standard mid-rollout.

- [ ] **Step 4: Write Sections 1–9 (the rules)**

Each section follows the exact anatomy:

```markdown
## <N>. <Topic>

<2-4 lines of rationale — what the rule serves>

**Rules:**
- Do <X>.
- Don't <Y>.
- When <edge case>, <decision>.

**Example:**
\```python
# Before
<bad>

# After
<good>
\```

**Checklist:**
- [ ] <check 1>
- [ ] <check 2>
- [ ] <check 3>
```

Content for each section:

- **Section 1 — Naming.** Verb-first for functions (`extract_pli`, not `pli_extractor`), noun-first for classes (`SheetPlanner`, not `PlanSheets`), concise descriptive names (`row_role`, not `the_role_of_a_row_in_a_sheet`), `_` prefix for private helpers, no version suffixes (`process_data_helper_v2` is a defect), match domain vocabulary (PLI, Stage, ANCHOR, CHILD).
- **Section 2 — Functions.** One job per function. Soft length target: **40 lines**. Override syntax: `# allow-long: <reason>` directly above the `def`. Decomposition heuristic: if you can name the helpers concisely in domain terms (`_check_reference_integrity`, `_check_row_uniqueness`), the split is right; if helpers need awkward names (`_part_one`, `_inner_loop`), the split is wrong — leave it. Pure functions preferred where reasonable; no hidden state mutation.
- **Section 3 — Docstrings.** Required on every public function and every non-trivial private. Format: one-line summary (imperative mood, ≤80 chars) then **blank line then Args/Returns/Raises only when non-obvious from signature**. Never restate the signature. Module docstrings briefly state the module's responsibility. Class docstrings state the class's invariant.
- **Section 4 — Comments.** "Why, not what." A comment is warranted when explaining a non-obvious constraint, a surprising workaround, or referencing an external spec/issue. Never reference plan-task names (`# SRP Task 17` is a defect). Never comment what a well-named identifier already conveys.
- **Section 5 — Type hints.** Mandatory on every public function signature. Modern syntax: `int | None`, not `Optional[int]`; `list[str]`, not `List[str]`; `dict[str, int]`, not `Dict[str, int]`. Use `typing.Protocol` for duck-typed interfaces; `TypeAlias` for repeating compound types; avoid `Any` — use a narrower type or genuine `object`.
- **Section 6 — Error handling.** Raise specific exceptions for errors; return `None` only when "not found" is part of the contract. No bare `except`. No `except Exception` without a logged reason and a re-raise. Validate inputs at module boundaries (router, public API); trust inside. Never swallow an exception silently.
- **Section 7 — Imports.** Three groups separated by blank lines: stdlib, third-party, local (`app.*`). Alphabetised within each group. Absolute imports only (`from app.models.extraction import PLI`, not `from .models.extraction`). Lazy imports inside functions are OK only when the dep is genuinely optional (large + may not be installed) or to break a circular import.
- **Section 8 — Module organization.** One clear responsibility per file. Public API at the top, helpers below. Function order: public functions in narrative order (caller before callee), private helpers after. When a file exceeds ~200 lines OR holds more than one cohesive concept, split. `__init__.py` re-exports only the public API of the package.
- **Section 9 — Test interaction.** Production code must (a) be testable without monkey-patching internals — accept dependencies through parameters or constructor injection; (b) not mutate global state at import time; (c) not assume a network connection or filesystem layout. Production code must NOT (a) branch on `if TESTING:` or environment flags meant for tests; (b) accept test-only kwargs; (c) reach into test fixtures.

- [ ] **Step 5: Write Section 10 — Master self-review checklist**

Distil Sections 1–9 into a single ~30-item checklist that a subagent runs against any file before commit. Group by Section number. Each item is a yes/no that can be answered in one scan of the file.

Example shape:

```markdown
## 10. Self-review checklist

Run this before every commit.

**Naming (S1):**
- [ ] All function names are verb-first.
- [ ] All class names are noun-first.
- [ ] No version suffixes (`_v2`), no `_helper`, no `_util` in names.
- [ ] All private helpers have a leading `_`.

**Functions (S2):**
- [ ] No function exceeds 40 lines (or has `# allow-long: <reason>`).
- [ ] Every function does one thing nameable in domain terms.
- ...
```

- [ ] **Step 6: Length + voice review**

Open the draft. Target is ~300 lines; under 250 is too thin, over 400 means trimming. Re-read with both audiences in mind:
- Could an LLM apply Section 10 to a file by following the bullets?
- Could a human pick up the doc cold and understand the rationale?

Trim anything that is not a rule, an example, or a check.

- [ ] **Step 7: Commit**

```bash
git add docs/CODING_STANDARD.md
git commit -m "docs(standard): draft CODING_STANDARD.md v1 (Phase 0 of refactor)"
```

---

## Task 2: Phase P — Pilot refactor of `plan_invariants.py`

**Files:**
- Modify: `app/services/validation/plan_invariants.py`

This file is the standard's first contact with real code. Goals: (a) validate the standard's rules work in practice; (b) demonstrate function decomposition; (c) surface any ambiguity in the standard before rollout.

**Current state:** 78 lines, 3 functions (`_e`, `_w`, `validate_invariants`), 0 docstrings, 55-line `validate_invariants` running 5 distinct checks inline.

- [ ] **Step 1: Read CODING_STANDARD.md (especially Section 10)**

Internalise the master checklist before opening the target file.

- [ ] **Step 2: Read `app/services/validation/plan_invariants.py` end-to-end**

Identify the 5 inline checks inside `validate_invariants`:

1. Reference integrity (ANCHOR rows shouldn't have `anchor_idx`; CHILD rows must point to a real ANCHOR).
2. Row uniqueness (no duplicate `row.idx`).
3. Header contiguity (header rows contiguous + data rows after them).
4. PLI block non-overlap (sorted blocks must not overlap by bbox).
5. Sub-row consistency (within a group, all members agree on whether `sub_row_role` is set).

- [ ] **Step 3: Decompose `validate_invariants` into 5 named helpers**

Extract each check into its own private function with a docstring. Final shape of the module:

```python
"""Tier 1 plan validators — structural invariants of a SheetPlan as a graph.

Errors here mean the plan is corrupt; the orchestrator should re-plan with
hints, not call PlanReviewer.
"""
from __future__ import annotations
from app.models.artifacts import SheetPlan, ValidationFinding
from app.enums.row_role import RowRole
from app.enums.validation_severity import ValidationSeverity
from app.core.logs import get_logger

log = get_logger(__name__)


def _error(check: str, msg: str) -> ValidationFinding:
    """Build an ERROR finding for the given check."""
    return ValidationFinding(check=check, severity=ValidationSeverity.ERROR, message=msg)


def _warn(check: str, msg: str) -> ValidationFinding:
    """Build a WARN finding for the given check."""
    return ValidationFinding(check=check, severity=ValidationSeverity.WARN, message=msg)


def _check_reference_integrity(plan: SheetPlan) -> list[ValidationFinding]:
    """Anchor rows must not carry anchor_idx; child rows must point at a real anchor."""
    ...


def _check_row_uniqueness(plan: SheetPlan) -> list[ValidationFinding]:
    """Each row.idx may appear at most once across plan.rows."""
    ...


def _check_header_contiguity(plan: SheetPlan) -> list[ValidationFinding]:
    """Header rows must form a contiguous range, and no data row may precede them."""
    ...


def _check_pli_block_non_overlap(plan: SheetPlan) -> list[ValidationFinding]:
    """Sorted by bbox start, no two pli_blocks may overlap."""
    ...


def _check_sub_row_consistency(plan: SheetPlan) -> list[ValidationFinding]:
    """Within a group, all members must agree on whether sub_row_role is set."""
    ...


def validate_invariants(plan: SheetPlan) -> list[ValidationFinding]:
    """Run all Tier 1 structural invariant checks against a SheetPlan.

    Returns the concatenated findings. ERROR severity means the plan is corrupt
    and the orchestrator should re-plan with hints rather than call PlanReviewer.
    """
    findings = [
        *_check_reference_integrity(plan),
        *_check_row_uniqueness(plan),
        *_check_header_contiguity(plan),
        *_check_pli_block_non_overlap(plan),
        *_check_sub_row_consistency(plan),
    ]
    if findings:
        log.info(
            "plan_invariants_findings",
            sheet=plan.sheet,
            error_count=sum(1 for f in findings if f.severity == ValidationSeverity.ERROR),
            warn_count=sum(1 for f in findings if f.severity == ValidationSeverity.WARN),
        )
    return findings
```

Notes on the decomposition:
- Rename `_e` → `_error` and `_w` → `_warn`. Single-letter helper names violate Section 1.
- The five `_check_*` helpers each get a one-line docstring matching Section 3.
- `validate_invariants` becomes a thin orchestrator: ~12 lines, single job (compose + log).
- Logic inside each helper is **lifted verbatim** from the original — no edits, no refactor. The body of `_check_reference_integrity` is the for-loop from lines 26–37 of the original, unchanged.

- [ ] **Step 4: Run Section 10 checklist**

Tick every box in `docs/CODING_STANDARD.md` Section 10. Fix anything that fails.

- [ ] **Step 5: Run `make test`**

```bash
make test
```

Expected: same number of tests pass as before (currently ~209). If anything fails, the decomposition introduced a behavior change — revert and try again.

- [ ] **Step 6: Self-review the diff**

```bash
git diff app/services/validation/plan_invariants.py
```

Confirm:
- The 5 helper bodies are character-for-character copies of the inline blocks (minus indentation).
- The new orchestrator just concatenates the helpers' outputs.
- No new conditionals, no reordered statements, no swapped exception types.

- [ ] **Step 7: Commit**

```bash
git add app/services/validation/plan_invariants.py
git commit -m "refactor(validation): apply coding standard to plan_invariants (pilot)"
```

- [ ] **Step 8: Pilot post-mortem**

Open `docs/CODING_STANDARD.md` and answer in your own notes (not in the commit):
- Did any rule feel awkward to apply?
- Did the soft length target (40) feel right? Too tight? Too loose?
- Was the docstring format clear enough?
- Did Section 10's checklist catch everything you'd want a reviewer to catch?

If answers raise real issues → Task 3. Otherwise → Task 4 (gate).

---

## Task 3: Phase R — Reconcile standard with pilot findings (conditional)

**Files:**
- Modify: `docs/CODING_STANDARD.md`

Execute only if the pilot post-mortem (Task 2 Step 8) surfaced real gaps. If the pilot went clean, **skip this task**.

- [ ] **Step 1: List the issues**

Write a short bullet list (in conversation, not committed): what specific rule was ambiguous, what failed to catch a problem, what felt over-prescriptive.

- [ ] **Step 2: Edit the standard**

For each issue, make the smallest edit that fixes it. Resist the urge to rewrite sections; surgical changes only.

- [ ] **Step 3: Decide: small or big amendment?**

- **Small amendment** (clarification, added bullet, tightened example): proceed to Step 4 — commit and continue.
- **Big amendment** (new rule, removed rule, changed length target): **re-pilot** by reverting Task 2's commit and re-running Phase P with the amended standard. Only after a clean re-pilot do you proceed.

- [ ] **Step 4: Commit**

```bash
git add docs/CODING_STANDARD.md
git commit -m "docs(standard): reconcile standard with pilot findings"
```

---

## ▶ HARD GATE — User approves the final `docs/CODING_STANDARD.md` ◀

**Do not start Task 4 (Phase 1) until the user has explicitly approved the contents of `docs/CODING_STANDARD.md`.** Surface the standard for review with the diff since Task 1's draft if any reconcile happened.

---

## Phase 1 — `models/` + `enums/` + `schemas/`

12 files. Skip empty `__init__.py` files (audited later in Task 59).

### Task 4: `app/enums/cell_dtype.py`

**Current state:** Single-purpose enum file. Apply Sections 1, 3 (module + class docstring), 7 (imports). Likely a small diff.

Follow the shared workflow above. Commit message: `refactor(enums): apply coding standard to cell_dtype`.

### Task 5: `app/enums/environment.py`

Follow the shared workflow. Commit: `refactor(enums): apply coding standard to environment`.

### Task 6: `app/enums/location_pattern.py`

Follow the shared workflow. Commit: `refactor(enums): apply coding standard to location_pattern`.

### Task 7: `app/enums/pli_mode.py`

Follow the shared workflow. Commit: `refactor(enums): apply coding standard to pli_mode`.

### Task 8: `app/enums/row_role.py`

Follow the shared workflow. Commit: `refactor(enums): apply coding standard to row_role`.

### Task 9: `app/enums/stage_scope.py`

Follow the shared workflow. Commit: `refactor(enums): apply coding standard to stage_scope`.

### Task 10: `app/enums/validation_severity.py`

Follow the shared workflow. Commit: `refactor(enums): apply coding standard to validation_severity`.

### Task 11: `app/schemas/extract.py`

**Current state:** Thin wrapper around `ExtractionResult`. Small file; mostly module docstring + verify imports.

Follow the shared workflow. Commit: `refactor(schemas): apply coding standard to extract`.

### Task 12: `app/schemas/health.py`

Follow the shared workflow. Commit: `refactor(schemas): apply coding standard to health`.

### Task 13: `app/models/workbook.py`

**Current state:** 55 lines, model defs. Apply Section 3 (model docstrings for each Pydantic class — state the invariant), Section 5 (type hints), Section 8 (module org). Don't add field-level docstrings unless the field's invariant is non-obvious from name + type.

Follow the shared workflow. Commit: `refactor(models): apply coding standard to workbook`.

### Task 14: `app/models/extraction.py`

**Current state:** 135 lines, 3 functions, 1 docstring, `_parse_flexible_date` 18 lines. Apply Section 3 to all classes (PLI, Stage, Source, ExtractionResult, Warning) — class docstring states the invariant of each. Don't add row-level docstrings to Pydantic fields.

Follow the shared workflow. Commit: `refactor(models): apply coding standard to extraction`.

### Task 15: `app/models/artifacts.py`

**Current state:** 263 lines, all Pydantic model defs (SheetPlan, RowSpec, KVAnchor, StageBandSpec, PliBlock, etc.). Largest file in the codebase but mostly model definitions — naming and class docstrings dominate.

Notes:
- Section 3: every model class gets a class docstring stating its invariant (one line, what does an instance of this class promise).
- Section 8: if the file exceeds ~300 lines after edits, **stop and surface** before splitting. Per the standard's amendment policy, a file split is a structural change that requires reviewer approval.

Follow the shared workflow. Commit: `refactor(models): apply coding standard to artifacts`.

### Task 16: Phase 1 end-of-phase verification

- [ ] Run `make eval`:

```bash
make eval > evals/runs/phase1-after.txt 2>&1
```

- [ ] Diff against the baseline captured before Phase 1 (from CLAUDE.md / pre-Phase-0 state). If the matrix shifted, **stop**: investigate. If unchanged, proceed.

- [ ] Tag the phase boundary for easy revert:

```bash
git tag refactor/phase1-complete
```

---

## Phase 2 — `config/` + `core/`

7 files.

### Task 17: `app/config/settings.py`

**Current state:** pydantic-settings-based config (53 lines). Section 3 on the Settings class; Section 5 on env var typing; Section 9 on test interaction (settings must accept overrides for tests).

Follow the shared workflow. Commit: `refactor(config): apply coding standard to settings`.

### Task 18: `app/core/logs.py`

**Current state:** 53 lines, structlog setup. Apply Section 3 (module + `configure_logging` docstring). Watch for Section 4 — any task-name references in comments.

Follow the shared workflow. Commit: `refactor(core): apply coding standard to logs`.

### Task 19: `app/core/middleware.py`

**Current state:** Request-id middleware. Section 3 (class docstring stating the middleware's responsibility), Section 5 (type hints on `dispatch`).

Follow the shared workflow. Commit: `refactor(core): apply coding standard to middleware`.

### Task 20: `app/core/pipeline_loader.py`

Follow the shared workflow. Commit: `refactor(core): apply coding standard to pipeline_loader`.

### Task 21: `app/core/prompt_loader.py`

Follow the shared workflow. Commit: `refactor(core): apply coding standard to prompt_loader`.

### Task 22: `app/core/telemetry.py`

**Current state:** 139 lines, **7 functions, 0 docstrings**. OTel Metrics SDK collectors + thin Noop fallbacks. High-priority for Section 3 (docstrings) — every collector and helper needs a one-line docstring stating what it measures. Section 1: the `_NoopMeter` and `_NoopInstrument` shim names are fine (they describe what they are).

Follow the shared workflow. Commit: `refactor(core): apply coding standard to telemetry`.

### Task 23: `app/core/tracing.py`

**Current state:** 214 lines, 12 functions, 3 docstrings, **82-line `configure_tracing`**. The biggest decomposition target outside the pilot. The function sets up:

1. Imports (try/except guard).
2. Idempotency check.
3. Endpoint resolution from arg/env.
4. Resource creation.
5. TracerProvider + BatchSpanProcessor + OTLPSpanExporter.
6. MeterProvider + PeriodicExportingMetricReader + OTLPMetricExporter.
7. LoggerProvider + BatchLogRecordProcessor + OTLPLogExporter.
8. Propagators (W3C + B3).
9. httpx auto-instrumentation.

Candidate helper extraction:
- `_resolve_otlp_endpoint(arg: str | None) -> str` — pulls the env-var resolution out.
- `_build_tracer_provider(endpoint: str, resource: Resource) -> TracerProvider`
- `_build_meter_provider(endpoint: str, resource: Resource) -> MeterProvider`
- `_build_logger_provider(endpoint: str, resource: Resource) -> LoggerProvider`
- `_install_propagators() -> None`
- `_install_httpx_instrumentation() -> None`

`configure_tracing` becomes a thin orchestrator that calls these in order. Stay verbatim on each helper's body — lift, don't refactor.

Follow the shared workflow. Commit: `refactor(core): apply coding standard to tracing`.

### Task 24: Phase 2 end-of-phase verification

- [ ] `make eval > evals/runs/phase2-after.txt 2>&1`; diff against `phase1-after.txt`. Investigate any shift.
- [ ] `git tag refactor/phase2-complete`.

---

## Phase 3 — `repositories/`

7 files.

### Task 25: `app/repositories/workbook_repo.py`

Follow the shared workflow. Commit: `refactor(repositories): apply coding standard to workbook_repo`.

### Task 26: `app/repositories/workbook_tools/_registry.py`

**Current state:** 71 lines, 9 functions, 1 docstring, 24-line `register`. Section 3 (every function needs a docstring), Section 2 (consider whether `register` can decompose — likely already single-job).

Follow the shared workflow. Commit: `refactor(repositories): apply coding standard to _registry`.

### Task 27: `app/repositories/workbook_tools/bulk_read.py`

**Current state:** 82 lines, 5 functions, 3 docstrings. Mostly compliant; finish docstring coverage and verify Section 5 type hints.

Follow the shared workflow. Commit: `refactor(repositories): apply coding standard to bulk_read`.

### Task 28: `app/repositories/workbook_tools/search.py`

Follow the shared workflow. Commit: `refactor(repositories): apply coding standard to search`.

### Task 29: `app/repositories/workbook_tools/structure.py`

**Current state:** 2/2 docstrings already. Likely a small diff confirming Sections 1, 5, 7. Could be a no-op commit if already compliant — if so, **don't commit an empty change**, just note "no changes needed" in the report and move on.

Follow the shared workflow with the no-op exception. Commit only if a real change was made.

### Task 30: `app/repositories/workbook_tools/survey.py`

**Current state:** 2/2 docstrings. Same no-op note as Task 29.

Follow the shared workflow. Commit only if changed.

### Task 31: `app/repositories/workbook_tools/targeted.py`

**Current state:** 3/3 docstrings — the cleanest file in the codebase. Probably another no-op pass. Verify imports, type hints.

Follow the shared workflow. Commit only if changed.

### Task 32: Phase 3 end-of-phase verification

- [ ] `make eval > evals/runs/phase3-after.txt 2>&1`; diff against `phase2-after.txt`.
- [ ] `git tag refactor/phase3-complete`.

---

## Phase 4 — `services/planner/`

6 files.

### Task 33: `app/services/planner/block_segmenter.py`

Follow the shared workflow. Commit: `refactor(planner): apply coding standard to block_segmenter`.

### Task 34: `app/services/planner/kv_anchor_detector.py`

Follow the shared workflow. Commit: `refactor(planner): apply coding standard to kv_anchor_detector`.

### Task 35: `app/services/planner/plan.py`

**Current state:** 157 lines, 4 functions, 0 docstrings, 55-line `run`. Function decomposition is likely. `run` orchestrates the planner pipeline — candidate helpers are the named stages already inside it.

Follow the shared workflow. Commit: `refactor(planner): apply coding standard to plan`.

### Task 36: `app/services/planner/row_classifier.py`

**Current state:** 138 lines. Apply Sections 3 and 2.

Follow the shared workflow. Commit: `refactor(planner): apply coding standard to row_classifier`.

### Task 37: `app/services/planner/stage_band_detector.py`

**Current state:** 126 lines.

Follow the shared workflow. Commit: `refactor(planner): apply coding standard to stage_band_detector`.

### Task 38: `app/services/planner/surveyor.py`

**Current state:** 104 lines.

Follow the shared workflow. Commit: `refactor(planner): apply coding standard to surveyor`.

### Task 39: Phase 4 end-of-phase verification

- [ ] `make eval > evals/runs/phase4-after.txt 2>&1`; diff against `phase3-after.txt`.
- [ ] `git tag refactor/phase4-complete`.

---

## Phase 5 — `services/agents/` + `services/validation/`

10 files (excluding `plan_invariants.py`, done in pilot).

### Task 40: `app/services/agents/_base.py`

**Current state:** 131 lines, 3 functions, **0 docstrings**, 69-line `run`. Big decomposition target. The agent runner orchestrates: build LLM request, invoke LLM, parse response into schema, handle retries on schema-validation failure. Each is a candidate helper.

Follow the shared workflow. Commit: `refactor(agents): apply coding standard to _base`.

### Task 41: `app/services/agents/field_namer.py`

**Current state:** 63 lines, 3 functions, **0 docstrings**, 21-line `_build_user_input`. Add docstrings, lift inline prompt-assembly logic into named helpers if it improves clarity.

Follow the shared workflow. Commit: `refactor(agents): apply coding standard to field_namer`.

### Task 42: `app/services/agents/layout_hinter.py`

**Current state:** 60 lines, 0 docstrings.

Follow the shared workflow. Commit: `refactor(agents): apply coding standard to layout_hinter`.

### Task 43: `app/services/agents/plan_reviewer.py`

**Current state:** 69 lines, 0 docstrings.

Follow the shared workflow. Commit: `refactor(agents): apply coding standard to plan_reviewer`.

### Task 44: `app/services/agents/sheet_classifier.py`

**Current state:** 59 lines, 0 docstrings.

Follow the shared workflow. Commit: `refactor(agents): apply coding standard to sheet_classifier`.

### Task 45: `app/services/validation/coverage_verifier.py`

**Current state:** 51 lines.

Follow the shared workflow. Commit: `refactor(validation): apply coding standard to coverage_verifier`.

### Task 46: `app/services/validation/field_dropout_verifier.py`

Follow the shared workflow. Commit: `refactor(validation): apply coding standard to field_dropout_verifier`.

### Task 47: `app/services/validation/header_match_verifier.py`

**Current state:** 65 lines.

Follow the shared workflow. Commit: `refactor(validation): apply coding standard to header_match_verifier`.

### Task 48: `app/services/validation/plan_statistics.py`

**Current state:** 85 lines, 0 docstrings.

Follow the shared workflow. Commit: `refactor(validation): apply coding standard to plan_statistics`.

### Task 49: `app/services/validation/source_cell_verifier.py`

**Current state:** 56 lines, 3 functions, 0 docstrings.

Follow the shared workflow. Commit: `refactor(validation): apply coding standard to source_cell_verifier`.

### Task 50: Phase 5 end-of-phase verification

- [ ] `make eval > evals/runs/phase5-after.txt 2>&1`; diff against `phase4-after.txt`.
- [ ] `git tag refactor/phase5-complete`.

---

## Phase 6 — `services/extraction.py` + `reconciler` + `applier` + `routers` + `main`

7 files. The orchestration tier — this is where eval regressions are most likely if anything is going to break.

### Task 51: `app/services/applier/apply_plan.py`

**Current state:** 229 lines, 10 functions, 1 docstring, 43-line `_read_stages`. Big file, high-traffic. Decomposition candidates inside `_read_stages` likely include: locating the stage band, iterating sub-rows, reading planned-date + sub-column cells, attaching source cells. Lift inline blocks into named helpers; do not change ordering.

**Special care:** this file is the dominant `make eval` consumer. After commit, run `make eval` BEFORE moving to the next task — even though phase verification is at end of phase.

Follow the shared workflow + the extra eval. Commit: `refactor(applier): apply coding standard to apply_plan`.

### Task 52: `app/services/llm_provider.py`

**Current state:** 184 lines, 11 functions, 2 docstrings, 55-line `complete_with_schema`. Anthropic SDK wrapper. Decomposition candidates: schema-inlining (`$ref` expansion), API call, retry-on-validation-failure, message-shape assembly.

Follow the shared workflow. Commit: `refactor(services): apply coding standard to llm_provider`.

### Task 53: `app/services/reconciler.py`

**Current state:** 53 lines, 3 functions, 3 docstrings. Mostly compliant.

Follow the shared workflow. Commit only if changed.

### Task 54: `app/services/extraction.py`

**Current state:** 229 lines, 4 functions, 1 docstring, 77-line `_plan_for_sheet`. The flagship orchestrator. Decomposition: `_plan_for_sheet` runs surveyor → row_classifier → kv_anchor_detector → stage_band_detector → block_segmenter → planner → validators → LayoutHinter (conditional) → PlanReviewer (conditional). Each phase is already named; helpers fall out naturally.

**Extra care:** this is the orchestrator. Validate the diff is character-for-character lifting from inline blocks into helpers, plus the orchestrator call sequence.

Follow the shared workflow. Commit: `refactor(services): apply coding standard to extraction`.

### Task 55: `app/routers/extract.py`

**Current state:** Router-level extract endpoint. Apply Section 9 (test interaction — accept dependencies via FastAPI `Depends`).

Follow the shared workflow. Commit: `refactor(routers): apply coding standard to extract`.

### Task 56: `app/routers/health.py`

Follow the shared workflow. Commit: `refactor(routers): apply coding standard to health`.

### Task 57: `app/main.py`

**Current state:** App entry point. Apply Section 8 (module org — startup-time wiring order is fine but should be explained).

Follow the shared workflow. Commit: `refactor(main): apply coding standard to main`.

### Task 58: Phase 6 end-of-phase verification

- [ ] `make eval > evals/runs/phase6-after.txt 2>&1`; diff against `phase5-after.txt`.
- [ ] `git tag refactor/phase6-complete`.

---

## Closing tasks

### Task 59: Audit all `__init__.py` files

16 `__init__.py` files exist in `app/`. Most are empty markers or one-line re-exports.

- [ ] **Step 1: List all `__init__.py` files**

```bash
find app -name "__init__.py" -not -path "*/__pycache__/*" | sort
```

- [ ] **Step 2: For each one**

Open it. Apply the standard:
- If empty: leave as is.
- If a re-export: ensure it follows Section 7 (alphabetised, absolute imports) and Section 8 (re-exports only public API).
- Add a one-line module docstring stating what the package contains, ONLY if the package's purpose isn't obvious from the directory name.

- [ ] **Step 3: Commit each changed `__init__.py` separately**

One file per commit, same as the rest of the rollout. Commit message: `refactor(<package>): apply coding standard to __init__`.

If no changes were needed, no commit.

### Task 60: Update `README.md` to reference the standard

- [ ] **Step 1: Read current README structure**

Look for the existing "Adding things" section or any developer-facing extension guide.

- [ ] **Step 2: Add a one-paragraph reference**

Add a short subsection (under "Adding things" or near it):

```markdown
### Coding bar

All new code in `tna-service/app/` follows [`docs/CODING_STANDARD.md`](./docs/CODING_STANDARD.md) — the project's standard for naming, docstrings, function decomposition, types, error handling, and module organisation. AI agents and human contributors run the master checklist in Section 10 of that file before each commit.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: link CODING_STANDARD.md from README"
```

### Task 61: Update `ARCHITECTURE.md` to reference the standard

- [ ] **Step 1: Read current ARCHITECTURE.md structure**

Find the most natural insertion point — likely after the overview, before the deep-dive sections, where current "principles" or "conventions" already live.

- [ ] **Step 2: Add a one-paragraph reference**

```markdown
## Coding standard

The codebase follows `docs/CODING_STANDARD.md` — Python-specific rules for naming, docstrings, function decomposition, type hints, error handling, imports, and module organisation. Section 10 of that document is the master checklist a reviewer or AI agent runs against any changed file before commit.
```

- [ ] **Step 3: Commit**

```bash
git add ARCHITECTURE.md
git commit -m "docs: reference CODING_STANDARD.md from ARCHITECTURE"
```

### Task 62: Flip design doc Status to `Implemented`

- [ ] **Step 1: Edit `docs/superpowers/specs/2026-05-14-coding-standard-design.md`**

Change the Status line:

```
**Status:** Approved, ready for implementation plan
```

to:

```
**Status:** Implemented (2026-05-14)
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-05-14-coding-standard-design.md
git commit -m "docs(spec): flip coding standard design Status to Implemented"
```

### Task 63: Final verification

- [ ] **Step 1: Final test run**

```bash
make test
```

Expected: all non-live tests pass (~209).

- [ ] **Step 2: Final eval run**

```bash
make eval > evals/runs/final.txt 2>&1
```

Compare to the pre-Phase-0 baseline. Matrix should be unchanged (within LLM noise — see spec risk table).

- [ ] **Step 3: Confirm no junk introduced**

```bash
grep -rn "TODO\|FIXME\|XXX" app/ | wc -l
```

Should match the pre-refactor count (or fewer).

- [ ] **Step 4: No commit**

This task is verification only.

---

## Plan summary

- **Tasks 1–3**: Standard draft + pilot + reconcile (3 tasks, 0–N reconcile commits).
- **HARD GATE**: User approves the standard.
- **Tasks 4–58**: 50 rollout tasks across 6 phases + 6 phase-end verification tasks. Each rollout task is one file, one commit.
- **Tasks 59–63**: `__init__.py` audit, README + ARCHITECTURE links, Status flip, final verification.

**Total commits expected:** ~55 (the standard + reconcile + 50 file refactors + closing). Subset of files in Phase 3 / 5 may be no-op (already compliant) and skip their commit.

**Tags created:** `refactor/phase1-complete` through `refactor/phase6-complete` for easy revert / bisect.
