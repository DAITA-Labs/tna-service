# Phase 3 — Migrate Tier 2 Structural Resolvers to Pickers

> **Scaffold plan.** Full bite-sized steps land after Phase 2 (picker base) merges; the migration shape depends on the base-class signatures Phase 2 nails down.

**Goal:** Replace every Tier 2 structural resolver (`AxisInferrer`, `LayoutComposer`, the pattern→semantic resolvers) with `Picker` subclasses + policy lists. The structure phase ends up reading exactly the same `StructureBag` / `LayoutHint` artifacts but produces them via pickers, surfacing per-decision verdict trails for the first time.

**Architecture:** One picker per Tier 2 resolver. Candidate generation moves to the picker's `candidates(...)` hook; the resolver's body becomes 3-8 policies. The existing structure-phase orchestrator becomes thinner — it just chains pickers via Haystack DSL.

**Spec sections:** §3 layer 1 (Structure), §9 layer 1 picker list.

**Depends on:** Phase 2 merged.

---

## File map

**Create (one picker + one policy module each):**
- `app/components/pickers/pli_axis_picker.py` + `app/policies/structure/pli_axis.py`
- `app/components/pickers/stage_axis_picker.py` + `app/policies/structure/stage_axis.py`
- `app/components/pickers/subfield_axis_picker.py` + `app/policies/structure/subfield_axis.py`
- `app/components/pickers/anchor_sheet_picker.py` + `app/policies/structure/anchor_sheet.py`
- `app/components/pickers/data_band_picker.py` + `app/policies/structure/data_band.py`

**Migrate (existing resolver files become deprecated; delete after picker parity):**
- `app/components/structure/axis_inferrer.py` → split per-axis into the three axis pickers above
- `app/components/structure/layout_composer.py` → folds into the data-band picker + anchor-sheet picker
- `app/components/structure/*resolvers*` → mapped one-to-one to pickers

**Modify:**
- `app/pipelines/structure_phase.py` (or current orchestrator path) — swap resolver components for pickers
- `tests/flow/structure_phase/*` — update fixtures to assert verdict trails are populated

---

## Task outline

1. **One picker at a time** — `PliAxisPicker` first (the smallest decision). TDD cycle: write policy tests, write picker test, swap the orchestrator call site.
2. **Per-picker A/B regression** — each migration runs the canvas eval; only merge if the migration matches legacy resolver output on every labelled family.
3. **Delete legacy resolvers** — after all axis pickers land, drop `axis_inferrer.py` and `layout_composer.py`.

---

## Validation

- Structure phase test suite still green.
- Canvas eval shows no regression after each picker swap.
- Every picker emits a non-empty verdict trail per fixture.
