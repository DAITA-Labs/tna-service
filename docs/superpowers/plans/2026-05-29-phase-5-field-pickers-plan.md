# Phase 5 — Field-Level Pickers (Identifier / Stages / Metadata / Unclaimed)

> **Scaffold plan.** Full bite-sized steps land after Phase 4 merges. This is the largest single phase — likely to be split into 4 sub-plans (one per picker) at expansion time.

**Goal:** Replace every Tier 4 per-canonical extractor (`IoNumberExtractor`, `QuantityExtractor`, etc.) with a single `IdentifierColumnPicker` that arbitrates across all 11 canonicals via one policy list. Add `StagesPicker`, `MetadataKvPicker`, and `UnclaimedColumnPicker`. The "no silent data loss" principle (spec §8) lands here: `UnclaimedColumnPicker` claims every tabular column not consumed by the identifier or stages pickers and emits `MetadataColumn` artifacts.

**Architecture:** One picker per field family; each picker's policies score column candidates with both per-canonical (`spec.value_constraints`) and cross-canonical (anti-dedup) signals. Retires the existing per-canonical extractor classes — their logic distills into ~30 reusable policies + helpers.

**Spec sections:** §3 layer 3 (Field locating), §8 (no data loss), §9 layer 3 picker list, §9 policy helpers.

**Depends on:** Phase 4 merged.

---

## File map (sketch)

**Create:**
- `app/components/pickers/identifier_column_picker.py` + `app/policies/field/identifier/` (one file per canonical + shared)
- `app/components/pickers/stages_picker.py` + `app/policies/field/stages.py`
- `app/components/pickers/metadata_kv_picker.py` + `app/policies/field/metadata.py`
- `app/components/pickers/unclaimed_column_picker.py` + `app/policies/field/unclaimed.py`
- `app/artifacts/plan.py` — `FieldLocation`, `StageBandPlan`, `MetadataColumn` dataclasses (per spec §4)

**Retire (after parity):**
- All `app/components/extractors/*Extractor` classes (Tier 4 per-canonical)
- `app/components/extractors/IdentifierArbiter` (folds into the picker's cross-canonical policy list)

---

## Task outline

1. **`FieldLocation` + `StageBandPlan` + `MetadataColumn` dataclasses** — pure data, no behavior. Fast TDD cycle.
2. **`IdentifierColumnPicker`** — biggest single deliverable. Build incrementally: io_number canonical first, then quantity, then add others. Each canonical's policies port from the corresponding extractor.
3. **`StagesPicker`** — stages_per_row map output.
4. **`MetadataKvPicker`** — KvBlocks → MetadataEntry list.
5. **`UnclaimedColumnPicker`** — runs LAST; reads which columns the identifier + stages pickers claimed and emits `MetadataColumn` records for the rest.
6. **A/B canvas-eval** — full regression across all four pickers vs. the existing Tier 4 chain.
7. **Delete Tier 4 extractors** after parity confirmed.

---

## Validation

- All four pickers green.
- Canvas eval matches or exceeds the current Tier 4 extractor chain on every labelled family.
- Every tabular column not claimed by identifier/stages appears as a `MetadataColumn` in the plan output.
