# Phase 2 — Picker Base + HeaderBandPicker Implementation Plan

> **Scaffold plan.** This file pins the goal, file map, and task outline. Full bite-sized steps will be written as a follow-up edit once Phase 1 (enum consolidation) lands and merges — the picker base imports the Phase 1 enums and would have to be rewritten if the enum names drifted.

**Goal:** Land the picker abstraction end-to-end on one decision (the header band), proving the candidate-loop + policy-list shape before the rest of the architecture follows.

**Architecture:** A `Picker` base class (Haystack `@component`) owns a `policies` list and an abstract `candidates(...)` method. Its `run(...)` iterates candidates, runs every policy against each, aggregates `PolicyVerdict.score_delta` minus eliminations, and emits a single winner + the full verdict trail. `HeaderBandPicker` is the first concrete subclass; its policies score row candidates for "where the header band sits."

**Tech Stack:** Python 3.12, Haystack 2.x, pytest.

**Spec sections:** §5 (picker template), §7 (`PolicyApplier` component), §9 layer 1 (structure pickers).

**Branch:** `canvas-plan-arch` (continues from Phase 1).

**Depends on:** Phase 1 plan complete and merged into `canvas-plan-arch`.

---

## File map

**Create:**
- `app/components/pickers/_base.py` — `Picker` abstract `@component` with `candidates(...)` hook + `run(...)` candidate loop
- `app/policies/_base.py` — `PolicyVerdict` dataclass (already typed in spec §4); helper `aggregate_verdicts(...)`
- `app/policies/_helpers.py` — initial helpers per §9 (`column_dtype_majority`, `row_dtype_majority`, `text_density`, etc. — first ~3 helpers HeaderBandPicker uses)
- `app/policies/structure/header_band.py` — first batch of policies (`prefer_text_dense_row`, `penalize_data_row`, `eliminate_below_first_date_strip`)
- `app/components/pickers/header_band.py` — `HeaderBandPicker(Picker)` concrete subclass
- `tests/unit/components/pickers/test_picker_base.py` — base-class candidate-loop behavior with synthetic policies
- `tests/unit/components/pickers/test_header_band_picker.py` — golden test on a small canvas fixture
- `tests/unit/policies/test_header_band_policies.py` — per-policy unit tests

**Modify:**
- `app/components/pickers/__init__.py` — export `Picker`, `HeaderBandPicker`
- `app/policies/__init__.py` — export `PolicyVerdict`, `aggregate_verdicts`
- `ARCHITECTURE.md` — add a "Pickers" section pointing to `app/components/pickers/_base.py`

---

## Task outline

1. **`PolicyVerdict` dataclass + `aggregate_verdicts` helper** — one TDD cycle. Frozen dataclass per spec §4.
2. **`Picker` base class** — abstract `candidates(...)`, concrete `run(...)` candidate loop, score floor handling, verdict-trail emission. Tested with two synthetic policies (one that scores, one that eliminates) against a fake candidate list.
3. **First three policy helpers in `app/policies/_helpers.py`** — `column_dtype_majority`, `row_dtype_majority`, `text_density`. Each gets a unit test that pins the helper output against a small fixture canvas.
4. **Three `header_band` policies** — `prefer_text_dense_row` (boost), `penalize_data_row` (penalty), `eliminate_below_first_date_strip` (filter). Each has its own unit test.
5. **`HeaderBandPicker` concrete subclass** — `candidates(...)` returns row indices in the anchor sheet's top N rows; uses the three policies above.
6. **Golden integration test** — small synthetic canvas, assert the picked header row matches expectation + verdict trail contains all three policy verdicts.
7. **Wire into the structure phase orchestrator** — replace the current header-band resolver call site with `HeaderBandPicker.run()` behind a feature flag (`use_picker_for_header_band: bool` on the pipeline tuning) so we can A/B vs the existing resolver.
8. **A/B regression run** — run the full canvas eval with the flag on/off, assert no regressions on labelled families.

---

## Validation

- All Phase 2 unit + integration tests green.
- A/B canvas-eval run shows the picker's header-band choices match (or beat) the legacy resolver on every labelled family.
- The verdict trail surfaces in the artifact for at least one fixture, demonstrating the audit-trail principle.

---

## Hand-off

After Phase 2 merges, **expand this scaffold** into bite-sized TDD tasks (mirroring the Phase 1 plan's structure) before dispatching subagents. The expansion edit is its own commit.
