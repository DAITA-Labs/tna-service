# 0003 — SheetRowPlanner (induction-then-apply)

**Date:** 2026-05-13
**Status:** Accepted

## Context

The Spec1 microservice used a `BoundaryFinder` LLM agent to determine PLI row boundaries. It emitted a `PLIBoundaries` artifact: a single `(data_start_row, data_end_row)` range + a `BoundaryPattern` enum + a string-matched total-row filter. This broke on real workbooks:

- **CHRISTIAN BERG** has 7 PLIs across two anchor-grouped sections separated by unmarked total rows. `BoundaryFinder` returned 3.
- **Orders Plan family** (new job-TNA, TNA DETAILS, NEW.xlsx) uses scattered KV identity blocks + stacked Plan/Action/Deviation stage bands — a layout the single-range artifact cannot express.
- Four `BoundaryPattern` enum values covered only four points in a much larger layout space. Every new family required a prompt tweak.

Root cause: row arithmetic is exactly what LLMs do poorly. The current split (LLM produces boundaries; Python applies them) is inverted. The right split is: deterministic Python produces boundaries from measurable sheet signals; LLM reviews and names.

## Decision

Replace `BoundaryFinder` + the pattern-dispatched `field_applier` + `stage_applier` with a `SheetRowPlanner` subsystem built on the **induction-then-apply** principle.

**Unified artifact: `SheetPlan`** — expresses any observed or anticipated layout via three orthogonal axes:
- PLI scope: `ROW_PER_PLI` | `SECTION_PER_PLI` | `SHEET_IS_PLI`
- Stage scope: `SHEET_LEVEL` | `SECTION_LOCAL` | `PLI_LOCAL`
- PLI height: `SINGLE_ROW` | `MULTI_ROW` (sub-rows: PLAN/ACTION/DEVIATION)

**Pipeline per sheet:**
1. `SheetSurveyor` (det) → `SheetSignals`
2. `SheetRowPlanner` (det) → `SheetPlan` (draft)
3. `validate_plan` Tier 1 (structural invariants, det, mandatory) + Tier 2 (statistical sanity, det, mandatory)
4. `LayoutHinter` (LLM, conditional on ambiguity) → `LayoutHints`
5. `PlanReviewer` (LLM judge, conditional on low confidence or validator warnings) → `PlanVerdict`
6. `FieldNamer` (LLM) → `CanonicalNameMap` (maps header labels to canonical field names)
7. `apply_plan` (det, 100% LLM-free) → `list[PLI]`

**`apply_plan` contract:** same inputs produce identical outputs every run; zero LLM calls; no external state beyond openpyxl reads; no silent fallbacks; dispatches on enums only.

**LLM-as-judge rule:** `PlanReviewer` fires only when Tier 1/2 validators warn, plan confidence < 0.85, or mode is a rarer `SECTION_PER_PLI` / `SHEET_IS_PLI`. Det wins on disagreement; LLM failure is non-blocking.

Implemented across ~30 tasks (commits 2026-05-13). Deleted: `LayoutFingerprinter`, `BoundaryFinder`, `IdentityLocator`, `QuantityDateLocator`, `StageLocator`, `field_applier`, `stage_applier`, pattern handlers, `BoundaryPattern` enum, `StageLayoutMode` enum.

## Consequences

**Easier:**
- CHRISTIAN BERG: 7 PLIs (was 3). New job-TNA Orders Plan family: 5 sheets × 1 PLI = 5 PLIs.
- LLM call count per sheet drops from ~5 to ~1-2 in the median case.
- Row arithmetic bugs are now Python bugs (testable, deterministic) rather than LLM prompt bugs.
- New layout families add rules in `app/services/planner/*.py`, not new prompts or enum cases.
- `apply_plan` is statically assertable to have no LLM imports (test enforced).

**Harder / constrained:**
- More deterministic code to maintain in the planner subsystem.
- Tier 1/2 validator coverage must be kept current as new layout patterns surface.
- `PlanReviewer` prompt quality affects plan corrections for rarer modes.

**What we gave up:**
- `LayoutFingerprinter` and `BoundaryFinder` agents (deleted). Their jobs are now done deterministically.
- The 4-pattern `BoundaryPattern` enum. Replaced by the 3-axis `SheetPlan` which is strictly more expressive.

## Alternatives considered

- **Improve the BoundaryFinder prompt.** Rejected: prompt iteration cannot fix row-arithmetic errors reliably; the problem is architectural, not a tuning gap.
- **LLM produces the full SheetPlan.** Rejected: LLMs are unreliable at structured row indexing; the plan must be verifiable against Tier 1/2 invariants before apply. A LLM-produced plan that violates `ReferenceIntegrity` would silently corrupt output.
- **Per-family classifiers.** Rejected: violates the structural-signal-routing principle (ADR-0001, principle 2). Each new family would require a new classifier.
