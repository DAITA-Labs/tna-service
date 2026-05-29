# Phase 6 — PlanAssembler + CanvasPlan + CanvasApplier

> **Scaffold plan.** Full bite-sized steps land after Phase 5 merges.

**Goal:** Stitch the layer outputs (structure → workbook → field pickers) into one `CanvasPlan` artifact, then build the deterministic `CanvasApplier` that walks the plan to produce PLIs. Wire the new `/extract_canvas_v2` endpoint end-to-end on the new chain.

**Architecture:** `PlanAssembler` is a Haystack component that ingests the verdicts + winners from earlier pickers and emits one `CanvasPlan`. `PlanCrossFieldPicker` runs after assembly to resolve cross-field constraints (e.g., the date-trio rule). `CanvasApplier` iterates `plan.pli_rows`, reads each `field_location` to pull the right cell per canonical, plus `metadata_columns` for per-row metadata. Output: `list[PLI]`.

**Spec sections:** §3 layers 4-6, §4 (`CanvasPlan` dataclass), §6 (CanvasApplier), §7 (PolicyApplier), §8 (no data loss).

**Depends on:** Phase 5 merged.

---

## File map

**Create:**
- `app/artifacts/plan.py` — extend with `CanvasPlan` dataclass (spec §4); `FieldLocation` etc. already added in Phase 5
- `app/components/plan/plan_assembler.py` — assembles `CanvasPlan` from picker outputs
- `app/components/plan/plan_cross_field_picker.py` — resolves cross-field constraints
- `app/components/plan/canvas_applier.py` — deterministic walk → `list[PLI]`
- `app/policies/cross_field/` — date trio, identifier dedup-across-rows, etc.
- `app/pipelines/extract_canvas_v2.py` — full pipeline DSL: tier 1-3 → pickers → assembler → cross-field → applier
- `app/routers/extract_canvas_v2.py` — `POST /extract_canvas_v2` endpoint (parallel to existing `/extract_canvas`)

**Modify:**
- `main.py` — register the new router
- `ARCHITECTURE.md` — note the new endpoint and chain

---

## Task outline

1. **`CanvasPlan` dataclass** — frozen, fully typed per spec §4.
2. **`PlanAssembler`** — consumes picker outputs, emits one `CanvasPlan` per cluster bundle.
3. **`PlanCrossFieldPicker`** — runs cross-field policies (date trio is the marquee one).
4. **`CanvasApplier`** — deterministic walk; output mirrors existing `CanvasReconciler` shape so downstream eval works unchanged.
5. **`/extract_canvas_v2` endpoint** — parallel to existing `/extract_canvas`, swap-able via a router config flag.
6. **End-to-end test** — one real xlsx fixture, hit `/extract_canvas_v2`, assert output matches a golden ExtractionResult.

---

## Validation

- `/extract_canvas_v2` returns a non-empty `ExtractionResult` for every labelled family.
- `CanvasPlan` artifact captured in capture/observability outputs for inspection.
- Date-trio cross-field policy demonstrably fires on the FA26 family fixture.
