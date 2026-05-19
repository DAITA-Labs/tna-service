# Symmetric planner→agent contract — design

**Date:** 2026-05-19
**Status:** Draft
**Supersedes:** Aspects of `2026-05-13-sheet-row-planner-design.md` (the bridge artifact channels for ROW_PER_PLI and SECTION_PER_PLI)

## Problem

Probing `/extract` across nine representative files in `dataset/` (one per layout family) reveals that extraction is broken or partial for **eight of nine** files. The pattern by `pli_mode`:

| Mode | Files in probe | PLIs | Canonical fields populated (out of 8) | Stages |
|---|---|---|---|---|
| `ROW_PER_PLI` | DKN, MOP, Christian Berg, Northern Reflections | 1–7 | **0/8** for all four | 0 (NR: 1) |
| `SECTION_PER_PLI` | FA26 YC & EUROPE T&A #1 | 16 | **0/8** | 0 |
| `SHEET_IS_PLI` | 63261-TNA, new job-TNA, NEW, TNA DETAILS | 1–10 | 3–4/8 | 18–20 |

Every file across the board reports `extraction_confidence: 0.00`. SHEET_IS_PLI is partially working; the other two modes return PLI shapes but no canonical data.

### Where the failure sits

The deterministic planner is mechanically right — modes are correctly chosen for 8/9 files, PLI counts are correct (Christian Berg returns the labeled 7), block segmentation produces the expected counts. The break is in **what the planner writes onto the `SheetPlan` artifact for `FieldNamer` and `apply_plan` to consume**:

| Mode | Identity channel on `SheetPlan` | Stage channel | Status |
|---|---|---|---|
| `SHEET_IS_PLI` | `kv_anchors[].field` | `stage_bands[].stage_cols` | populated ✅ |
| `ROW_PER_PLI` | nothing — column headers live only as cell values in `header_rows`, never lifted onto the artifact | tall_sub_rows handled; single-row + multi-row strip detection missing | unpopulated ❌ |
| `SECTION_PER_PLI` | `pli_blocks[].identity` (should carry KVAnchors per block) | `pli_blocks[].stage_bands` | empty — segmenter doesn't fill ❌ |

`FieldNamer._build_user_input` collects labels from `kv_anchors`, `pli_blocks[].identity`, and `stage_bands[].stage_cols`. For ROW_PER_PLI, all three sources are empty by design (plan.py:192 explicitly zeroes `kv_anchors` for non-SHEET_IS_PLI modes; `pli_blocks=[]` in this mode). The LLM is sent a prompt with **no labels and no stage headers**, validly returns an empty `CanonicalNameMap`, and `apply_plan` then has nothing to map raw column-header text to canonical fields. All values land in `metadata` keyed by raw header text. `extraction_confidence` collapses to 0.0 because per-PLI `confidence={}` is never written.

### Root cause

The `SheetPlan` artifact was designed around the SHEET_IS_PLI case. The contract is **under-specified for ROW_PER_PLI and SECTION_PER_PLI**: the planner discovers labels and stage strips but has no artifact slot to surface them in those modes. The deterministic detectors, the LLM agents, and `apply_plan` are each behaving correctly given their inputs — the bridge between them is the bug.

## Goal

Make every file in `dataset/` produce an `ExtractionResult` with populated canonical fields, real stages, and an `extraction_confidence` that reflects quality. No "empty husk" PLIs. The mechanism: extend the `SheetPlan` artifact symmetrically across the three `pli_mode`s so that `FieldNamer` and `apply_plan` see a populated identity channel and a populated stage channel for every mode.

### Success criteria

1. Every of the 24 files in `dataset/` returns a non-empty `ExtractionResult` — every PLI has ≥1 populated canonical field OR an explicit Warning explaining the gap.
2. `extraction_confidence > 0.4` on any file where ≥1 canonical field extracts.
3. `pytest tests -q` (non-live) green; `pytest tests -m live` green against the real Anthropic API; `make eval` shows monotonic improvement on every previously-labelled file.
4. ADR-0003 invariants preserved (`apply_plan` is 100% deterministic and statically asserted; LLM-as-reviewer/namer; det planner produces row arithmetic).
5. `docs/CODING_STANDARD.md` §10 checklist passes on every file touched.

## Non-goals

- Changing the `POST /extract` HTTP surface — request and response shapes stay.
- Adding new fields to `PLI` or `Stage` output models — output schema is unchanged.
- New LLM agents — `SheetClassifier`, `LayoutHinter`, `PlanReviewer`, `FieldNamer` set stays.
- Adding new workbook tools — existing 10-tool `TOOL_REGISTRY` is unchanged.
- Per-family or supplier-name routing — structural-signal routing (PRINCIPLES §2) remains the rule.
- Fixing the MOP Compass Pro "1 PLI" planner-misclassification — separate failure mode, addressed post-Phase-1.

## Design

### Shape

One structural fix: extend `SheetPlan` so the three `pli_mode`s feed `FieldNamer` and `apply_plan` symmetrically.

```
                          ┌──────────────────────────────────────┐
                          │     SheetPlan (extended contract)    │
                          ├──────────────────────────────────────┤
                          │  shared                              │
                          │   • pli_mode, identity_column        │
                          │   • header_rows, rows                │
                          │   • stage_bands  (all 3 modes)       │
                          │                                      │
                          │  channel A — header_labels  [NEW]    │
                          │   populated in ROW_PER_PLI           │
                          │                                      │
                          │  channel B — kv_anchors              │
                          │   populated in SHEET_IS_PLI          │
                          │                                      │
                          │  channel C — pli_blocks               │
                          │   each carries identity + bands      │
                          │   populated in SECTION_PER_PLI       │
                          │   (segment_blocks fill)              │
                          └─────────┬────────────────────────────┘
                                    │  All channels FieldNamer-readable.
                                    │  apply_plan dispatches per mode but
                                    │  reads the same union of labels.
                                    ▼
                       FieldNamer ─►  CanonicalNameMap + confidence per label
                                    │
                                    ▼
                       apply_plan ─►  PLI with canonical fields + confidence
```

### Bridge artifact changes (`app/models/artifacts.py`)

```python
class HeaderLabel(BaseModel):
    """A column header label discovered in a sheet's header rows."""
    model_config = ConfigDict(extra="ignore")
    raw: str          # cell value, stripped
    col: str          # column letter (A, B, ..., AA)
    row: int          # row the label was read from
    confidence: float = 0.85   # header-inferred, medium default

class StageColumn(BaseModel):
    """One stage in a wide_sub_columns band, with primary col + sub-cols."""
    name: str                              # raw stage name, e.g. "CUTTING"
    name_cell: str                         # "U2"
    primary_col: str                       # column for planned_date
    sub_columns: dict[str, str] = Field(default_factory=dict)
    # {raw sub-label → col letter}, e.g. {"Actual": "V", "Qty": "W"}

class StageBandSpec(BaseModel):
    # existing fields unchanged
    ...
    stage_columns: list[StageColumn] = Field(default_factory=list)   # NEW canonical
    stage_cols: dict[str, str] = Field(default_factory=dict)         # deprecated alias for one release

class KVAnchor(BaseModel):
    # existing fields unchanged
    ...
    confidence: float = 0.95   # high-confidence by location

class CanonicalNameMap(BaseModel):
    field_labels: dict[str, str] = Field(default_factory=dict)
    stage_names: dict[str, str] = Field(default_factory=dict)
    stage_subfield_labels: dict[str, str] = Field(default_factory=dict)   # NEW
    # raw sub-label → canonical Stage field (e.g. "Actual" → "actual_date",
    # "Plan Qty" → "quantity", "Remarks" → "remarks")
    field_confidence: dict[str, float] = Field(default_factory=dict)     # NEW
    stage_confidence: dict[str, float] = Field(default_factory=dict)     # NEW

class SheetPlan(BaseModel):
    # existing fields unchanged
    ...
    header_labels: list[HeaderLabel] = Field(default_factory=list)   # NEW
```

### Channel ↔ mode matrix

| Mode | Identity | Stage |
|---|---|---|
| `ROW_PER_PLI` | `header_labels` | `stage_bands[].stage_columns` |
| `SHEET_IS_PLI` | `kv_anchors` | `stage_bands[].stage_columns` |
| `SECTION_PER_PLI` | `pli_blocks[].identity` | `pli_blocks[].stage_bands[].stage_columns` |

### Two stage band sub-layouts

| Sub-layout | Stage names | Sub-field labels | Resolver |
|---|---|---|---|
| `wide_sub_columns` | top header row, across columns | next header row, in `sub_columns` of each `StageColumn` | `_read_wide_stage_column` (one row per PLI; reads primary_col into `planned_date`, iterates sub_columns) |
| `tall_sub_rows` | top header row, across columns | down rows beneath, via `band.sub_rows` | `_read_tall_stage_column` (multiple rows per PLI; reads `band.sub_rows["plan"]` into `planned_date`, iterates remaining roles) |

Files in dataset/ by sub-layout: CB, DKN, Compass Pro, Northern Reflections are `wide_sub_columns`; 63261-TNA, new job-TNA, NEW, TNA DETAILS are `tall_sub_rows`. `_read_tall_stage_column` is unchanged.

### Sub-detector changes

**`app/services/planner/plan.py` — new `_collect_header_labels` step:**
After `detect_stage_bands` runs, walk every column not claimed by a stage band's `primary_col`/`sub_columns` and harvest the first non-empty string from `plan.header_rows`. Populates `plan.header_labels` for ROW_PER_PLI; empty for other modes.

```python
def _collect_header_labels(ws, plan: SheetPlan) -> list[HeaderLabel]:
    """Lift identity-column header strings from header_rows into the artifact."""
    if plan.pli_mode is not PliMode.ROW_PER_PLI:
        return []
    claimed: set[str] = set()
    for band in plan.stage_bands:
        for sc in band.stage_columns:
            claimed.add(sc.primary_col)
            claimed.update(sc.sub_columns.values())
    labels: list[HeaderLabel] = []
    for c_idx in range(1, (ws.max_column or 0) + 1):
        col = get_column_letter(c_idx)
        if col in claimed:
            continue
        for h_row in plan.header_rows:
            v = ws.cell(row=h_row, column=c_idx).value
            if isinstance(v, str) and v.strip():
                labels.append(HeaderLabel(raw=v.strip(), col=col, row=h_row))
                break
    return labels
```

**`app/services/planner/block_segmenter.py` — populate `identity` + `stage_bands` per block:**
Currently emits `PliBlock(bbox=…)` with empty `identity` and `stage_bands`. Fix: after computing block boundaries, partition the workbook-level `kv_anchors` and `stage_bands` by row range and attach to each block.

```python
def segment_blocks(rows, kv_anchors, blank_gaps, stage_bands) -> list[PliBlock]:
    boundaries = _detect_block_boundaries(rows, blank_gaps)   # unchanged
    blocks: list[PliBlock] = []
    for i, (start, end) in enumerate(boundaries):
        block_identity = [
            kv for kv in kv_anchors
            if start <= _row_of_cell(kv.value_cell) <= end
        ]
        block_bands = [
            band for band in stage_bands
            if start <= band.sub_header_row <= end
        ]
        blocks.append(PliBlock(
            id=i, bbox=(start, end),
            identity=block_identity,
            stage_bands=block_bands,
        ))
    return blocks
```

The existing `_segment_pli_blocks_if_applicable` in plan.py already returns `stage_bands_sheet=[]` for SECTION_PER_PLI mode, so sheet-level bands are emptied once attached to blocks. Unchanged.

**`app/services/planner/stage_band_detector.py` — `wide_sub_columns` paths:**
Two new code paths, both vocab-anchored. The existing `tall_sub_rows` detection stays.

- **Single-row strip** (CB-style). Scan each `header_rows[i]` for a contiguous run of cells whose text matches stage vocabulary. Minimum threshold: ≥3 adjacent stage-vocab hits to declare a band. Once a run is found: one `StageBandSpec` with `layout_mode="wide_sub_columns"`. `sub_header_row = i + 1` if row i+1 has non-stage-vocab strings under the run, else `sub_header_row = i`. Every cell in the run becomes a `StageColumn(name=text, name_cell=addr, primary_col=col)`. `sub_columns` from row i+1 non-empty cells under each stage's merged extent.
- **Two-row header** (DKN/Compass-style). Detected when `header_rows` has ≥2 entries and the run-scan finds stage vocab in the top row and sub-field vocab (`plan, actual, remarks, qty, approved, …`) in the row below. Per stage: read merged-cell extent in the top row to get its horizontal span; `primary_col` is the leftmost col in the span; `sub_columns = {row_i+1_cell_text: col}` for every non-empty cell within the span.

Both paths fall through to the existing tall_sub_rows detector if no band is declared.

### FieldNamer + apply_plan changes

**`FieldNamer._build_user_input` becomes mode-agnostic and value-aware.**
Reads from the union of `header_labels`, `kv_anchors`, `pli_blocks[].identity`, and `stage_columns` across sheet and block scopes. Includes a small sample of values (k=3 per identity label) so the LLM can name labels by inference when prompt vocab doesn't match.

```python
def _build_user_input(ctx, inputs) -> str:
    plan: SheetPlan = inputs["plan"]
    ws = ctx.wb[plan.sheet]

    identity = []   # list of (raw_label, col_letter)
    identity += [(hl.raw, hl.col) for hl in plan.header_labels]
    identity += [(kv.field, _col_of(kv.label_cell)) for kv in plan.kv_anchors]
    for blk in plan.pli_blocks:
        identity += [(kv.field, _col_of(kv.label_cell)) for kv in blk.identity]

    stage_names: list[str] = []
    sub_field_labels: set[str] = set()
    for band in plan.stage_bands + [b for blk in plan.pli_blocks for b in blk.stage_bands]:
        for sc in band.stage_columns:
            stage_names.append(sc.name)
            sub_field_labels.update(sc.sub_columns.keys())

    samples = _sample_values(ws, plan, identity, k=3)
    return _format_markdown(plan.sheet, identity, stage_names, sub_field_labels, samples)
```

**`FieldNamer` prompt** (`app/prompts/workflow/field_namer.md`) gains:
- Expanded canonical field list covering observed metadata keys (`buyer, season, factory, article_no, price, balance_qty, buyer_po_no, fabric_quality, cut_qty, sewing_qty, shipped_qty, etd_ex_factory, sample_dispatch, …`).
- New section: canonical stage sub-field names (`planned_date, actual_date, approval_date, received_date, approved_qty, quantity, remarks, deviation_days`).
- Output schema mentions optional `stage_subfield_labels` / `field_confidence` / `stage_confidence`. LLM can return them or leave empty.

The "ignore" sentinel for un-mappable labels stays.

**`app/services/applier/apply_plan.py` — three deltas:**

A. `_emit_single_row_pli` reads from `plan.header_labels` instead of re-reading header_rows cells. Cleaner separation; no behaviour change.

B. `_read_wide_stage_column` iterates `sub_columns` and routes them. primary_col → `planned_date`. Sub-columns canonicalised via `name_map.stage_subfield_labels`: canonical Stage fields (`quantity`) write to Stage directly; everything else goes to `Stage.metadata`.

```python
def _read_wide_stage_column(ws, band, stage_col, pli_row, name_map):
    canonical_stage = name_map.stage_names.get(stage_col.name, stage_col.name)
    if canonical_stage == "ignore":
        return None
    pv, pa = _read_with_merge(ws, pli_row, column_index_from_string(stage_col.primary_col))
    if pv is None:
        return None
    metadata, source_cells, stage_fields = {}, {"planned_date": pa}, {}
    for raw_sub, col in stage_col.sub_columns.items():
        canonical_sub = name_map.stage_subfield_labels.get(raw_sub, raw_sub)
        if canonical_sub == "ignore":
            continue
        v, addr = _read_with_merge(ws, pli_row, column_index_from_string(col))
        if v is None:
            continue
        if canonical_sub in Stage.model_fields and canonical_sub != "name":
            stage_fields[canonical_sub] = v
        else:
            metadata[canonical_sub] = v
        source_cells[canonical_sub] = addr
    return Stage(
        name=canonical_stage,
        planned_date=pv if isinstance(pv, (date, datetime)) else None,
        section=band.name, metadata=metadata,
        source={"sheet": ws.title, "rows": [pli_row], "cells": source_cells},
        **stage_fields,
    )
```

C. Every value write resolves a confidence number via `_resolve_confidence`. Calibration seed: KV anchor 0.95 / header label 0.85 / stage subfield 0.80 / metadata fallback 0.40. LLM-supplied per-field confidence wins when present.

`apply_plan` dispatch table on `pli_mode` is unchanged. `_apply_section_per_pli` and `_apply_sheet_is_pli` inherit the same `_emit_single_row_pli` / `_read_wide_stage_column` improvements. `_read_tall_stage_column` is unchanged. The static-analysis test (`tests/unit/applier/test_apply_plan_no_llm_imports.py`) continues to pass.

### Error handling & graceful degradation

| Failure | Behaviour |
|---|---|
| FieldNamer LLM call fails | Empty `CanonicalNameMap()` returned; `plan.header_labels` still flows to apply_plan; labels land in `metadata[raw_label]`. Better than empty husk; worse than success. |
| `stage_band_detector` finds no band | `plan.stage_bands=[]`; `header_labels` covers every column. Identity extracts; stages remain empty. PLI is partial-but-useful. |
| Novel supplier vocab | Label surfaces in prompt with 3 sample values; LLM frequently infers canonical name from values. Hallucinations caught by `SourceCellVerifier`. |
| Empty SECTION_PER_PLI block (no kv_anchors inside bbox) | Emits PLI with `metadata={}` + Warning `empty_block: block #N had no identity anchors`. Surfaced; not silently dropped. |
| New T1 invariant `exactly_one_identity_channel` violated | ERROR finding; triggers existing `LayoutHinter` re-plan loop. |
| New T1 invariant `mode_channel_consistency` violated | ERROR; triggers re-plan loop. |
| `header_labels` empty in ROW_PER_PLI | WARN; triggers `PlanReviewer` (existing path). |

All failures either surface as Warnings on `ExtractionResult`, trigger an existing re-plan/PlanReviewer loop, or fall back to `metadata` (visible to API consumer). `apply_plan`'s never-raises contract is preserved.

### New Tier 1 invariants in `validate_plan`

- **`exactly_one_identity_channel`** — exactly one of `header_labels`, `kv_anchors`, `pli_blocks` is non-empty. ERROR.
- **`mode_channel_consistency`** — `pli_mode` matches populated channel (`ROW_PER_PLI ↔ header_labels`, `SHEET_IS_PLI ↔ kv_anchors`, `SECTION_PER_PLI ↔ pli_blocks`). ERROR.

Both feed the existing re-plan loop. No new orchestrator paths.

## Testing strategy

Per `docs/TESTING.md`. Five tiers, fixture-driven.

### New unit tests

| Test file | Asserts |
|---|---|
| `tests/unit/models/test_artifacts_new_shape.py` | `HeaderLabel` / `StageColumn` validate; `SheetPlan` accepts defaults; `CanonicalNameMap` accepts optional confidence dicts |
| `tests/unit/planner/test_header_label_collector.py` | `_collect_header_labels` skips claimed stage cols, scans top-to-bottom per column, returns empty for non-ROW_PER_PLI modes |
| `tests/unit/planner/test_stage_band_detector_wide.py` | Single-row strip detected with ≥3 vocab hits; two-row header populates sub_columns via merge-extent walk; insufficient hits → no band |
| `tests/unit/planner/test_block_segmenter_partition.py` | bbox-filtered kv_anchors land in correct block; stage_bands assigned by sub_header_row range |
| `tests/unit/applier/test_read_wide_stage_column_sub_cols.py` | sub_column values route to Stage fields when canonical ∈ Stage.model_fields, else metadata; "ignore" sub-labels skipped |
| `tests/unit/applier/test_resolve_confidence.py` | LLM-supplied confidence wins; source-type defaults used otherwise |
| `tests/unit/validation/test_plan_invariants_new.py` | `exactly_one_identity_channel` ERROR; `mode_channel_consistency` ERROR; happy-path no findings |

### New fixtures

Per `docs/TESTING.md` §2 (one builder + one expected.json per scenario):

| Fixture | Tier coverage | Shape |
|---|---|---|
| `row_per_pli_wide_single_row_strip` | flow, e2e | CB-style: 5 identity cols + 4 stage cols in one row + 1 "Actual" sub-col |
| `row_per_pli_wide_two_row_strip` | flow, e2e | DKN-style: 2 stage cols each with merged top row + Plan/Actual sub-cols |
| `row_per_pli_no_stage_band` | flow, failure | Identity-only sheet; asserts header_labels populated, stage_bands=[], Warning `no_stage_band_detected` |
| `section_per_pli_blocks_with_identity` | flow, e2e | Two blocks with KV identity; asserts segment_blocks populates identity per block |
| `failure_segmenter_block_empty` | flow, failure | One block with no kv_anchors inside bbox; asserts PLI emitted + Warning `empty_block` |
| `failure_multiple_identity_channels` | flow, failure | Synthetic plan with both header_labels AND kv_anchors; T1 ERROR |

### Updated existing tests

- `tests/unit/applier/test_apply_plan_no_llm_imports.py` — must still pass; static AST scan untouched.
- Existing ROW_PER_PLI fixtures (`expected/*.json`) gain a `header_labels` count assertion. ~6 fixtures, one-line additive edit each.
- FakeLLM canned responses for FieldNamer agent tests gain optional `stage_subfield_labels` / `field_confidence` keys.

### Agent tier

| Test | Asserts |
|---|---|
| `tests/agent/test_field_namer_row_per_pli_input.py` | When `plan.header_labels` populated, prompt body contains an `"## Identity labels detected:"` section listing raw + col + sample values |
| `tests/agent/test_field_namer_sub_field_labels.py` | When stage_columns have sub_columns, prompt body lists sub-labels separately; FakeLLM `stage_subfield_labels` map wires through to apply_plan |
| `tests/agent/test_field_namer_value_sampling.py` | `_sample_values` returns ≤k samples, skips nulls, caps string length, stable order |

The 4 agent-failure sub-categories from TESTING.md §5 (raise / wrong-type / missing-required / extra-fields) share `tests/agent/test_field_namer_failure.py` — one parametrize entry added per new shape.

### E2E tier

Each new fixture with `layer_expectations.e2e` parametrizes the existing full-pipeline test, asserting:
- `len(result.plis) == expected_count`
- Canonical fields populated for the first PLI
- Stages emitted with canonical names
- `extraction_confidence > 0.5`
- No empty husks

### Live tier — real Anthropic API

```python
@pytest.mark.live
@pytest.mark.parametrize("xlsx", [
    "CHRISTIAN BERG- T&A.xlsx",
    "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
    "FA26 YC & EUROPE T&A #1.xlsx",
    "NORTHERN REFLECTIONS- T&a.xlsx",
])
def test_live_extraction_produces_canonical_fields(xlsx):
    result = extract(Path("dataset") / xlsx)
    assert len(result.plis) >= 1
    assert any(p.io_number for p in result.plis), f"{xlsx}: no io_number"
    assert any(p.style_code for p in result.plis), f"{xlsx}: no style_code"
    assert any(p.stages for p in result.plis), f"{xlsx}: no stages"
    assert result.extraction_confidence > 0.4, f"{xlsx}: conf={result.extraction_confidence}"
```

### Eval framework

Labels added in Phase 3 for currently-unlabelled families. `make eval` becomes the Phase-1 exit gate: scoreboard must show monotonic improvement on every previously-labelled file. Target ≥ 0.7 `field_recall` + `stage_recall` per family.

## Rollout phasing

### Phase 1 — Symmetric artifact contract (the structural fix)

| Step | What lands | Verification |
|---|---|---|
| 1.1 | Schema deltas in `artifacts.py` (additive only) | unit tests for new types; existing tests untouched |
| 1.2 | `stage_band_detector` — wide_sub_columns paths | unit fixtures: CB strip, DKN two-row; tall_sub_rows unchanged |
| 1.3 | `block_segmenter` — bbox partition fill | FA26-shaped fixture asserts non-empty blocks |
| 1.4 | `plan.py` — `_collect_header_labels` + new T1 invariants | flow tests for ROW_PER_PLI fixtures show populated `header_labels` |
| 1.5 | `apply_plan` — read from `header_labels`; route sub_columns | `test_apply_plan_no_llm_imports` still passes |
| 1.6 | `apply_plan` — per-field `PLI.confidence` writes | `extraction_confidence ≠ 0.0` on any working file |
| 1.7 | `FieldNamer` — mode-agnostic `_build_user_input` + value sampling | agent test confirms prompt shape |
| 1.8 | `expected.json` updates across ROW_PER_PLI fixtures | `make test` green; ~209 → ~225 tests |
| 1.9 | Live regression: 4 broken-family files | `pytest tests -m live -q` against real API |

**Phase 1 exit bar:** all 24 dataset files return non-empty PLIs (or explicit Warnings); `make test` green; `pytest -m live` green; `make eval` shows monotonic improvement on every previously-labelled file.

### Phase 2 — Vocab + calibration polish

- 2.1 FieldNamer prompt vocab expansion drawn from observed `metadata` keys in the 9-file probe.
- 2.2 Stage sub-field canonical list expansion (`planned_date, actual_date, approval_date, received_date, approved_qty, quantity, remarks, deviation_days`).
- 2.3 Confidence calibration against eval data once Phase 3 has labels. Target Spearman corr ≥ 0.4 between `extraction_confidence` and ground-truth `field_recall`.
- 2.4 `PlanReviewer` confidence threshold review using telemetry.

### Phase 3 — Labels + eval gate

- 3.1 Author labels in `dataset/extracted/` for `63261-TNA`, `new job-TNA`, `FA26 YC & EUROPE T&A #1`, `20260129 DKN AW26 DROP 2 …`, `NORTHERN REFLECTIONS- T&a`.
- 3.2 `make eval`: scoreboard with ≥ 0.7 `field_recall` + `stage_recall` per labelled family.
- 3.3 Baseline matrix committed to `evals/runs/` as the Phase-1 exit artefact.

### Open / deferred (post-Phase 3)

- MOP Compass Pro "1 PLI" misclassification — likely surveyor / row_classifier issue. Investigate after Phase 1 reveals what mode it now lands in.
- `LabelScout` agent (Approach B from brainstorm) — only if Phase 1+2 still leaves gaps with evidence.
- Stage band detector emitting per-band confidence reflecting vocab-match strength.
- SECTION_PER_PLI per-block re-detection (vs current partition-by-bbox) — only on evidence of band-crossing-block ambiguity.

## Documentation updates (per `docs/PRINCIPLES.md` §8)

At the *end* of each phase, not before:

| Phase end | Docs |
|---|---|
| Phase 1 | `ARCHITECTURE.md` bridge-artifact + planner sections; new ADR `0006-symmetric-artifact-contract.md`; `CLAUDE.md` "Current state" line |
| Phase 2 | `app/prompts/workflow/field_namer.md` (the change itself); `ARCHITECTURE.md` agent-table footnote about value sampling |
| Phase 3 | `docs/SPEC.md` success-criterion #2 (eval pass) crossed off; `README.md` "What it does" updated if user-facing |

## Risk register

| Risk | Mitigation |
|---|---|
| Phase 1 breaks an existing-working SHEET_IS_PLI fixture | Phase 1 is purely additive on the artifact contract. `stage_cols` flat alias stays for one release. Existing `_read_tall_stage_column` unchanged. CI catches regressions before merge. |
| LLM hallucinates canonical names from value samples | New names land in `metadata` (no-op) or hit `if canonical in PLI.model_fields` guard and fall through. `SourceCellVerifier` catches mismatches. |
| Calibration wrong → `extraction_confidence` lies | Phase 2.3 tunes against eval data. Until then, monotonic ranking (more fields → higher conf) is already an improvement on flat 0.0. |
| `make eval` regression on Compass Pro (independent bug) | Live test asserts ≥1 PLI; Compass flagged in open bucket; no Phase 1 commit lands if matrix regresses on previously-passing files. |
| Coding-standard checklist slows iteration | ~6 min per file × ~12 files in Phase 1 = ~1h total. Bounded cost; reviewer confidence benefit. |

## Coding standard adherence (`docs/CODING_STANDARD.md`)

Every new/changed file runs §10 checklist before commit:

- **S1 Naming**: verb-first functions (`_collect_header_labels`); noun-first classes (`StageColumn`); no version suffixes; canonical domain terms (`PLI`, `Stage`, `ANCHOR`, `CHILD`).
- **S2 Functions**: 40-line cap. `_emit_single_row_pli` (already near cap) gets a new helper `_route_subfield_value()`; sub_columns iteration goes there, not inline.
- **S3 Docstrings**: every public function + class + module. Private helpers >10 lines or with side effects also documented.
- **S4 Comments**: no plan-task references (`# Phase 1 task` etc.). Comments explain WHY (constraint, workaround, spec ref), not WHAT.
- **S5 Type hints**: modern syntax (`list[X]`, `X | None`); no `typing.Optional/List/Dict/Tuple/Union`; no `Any`.
- **S6 Errors**: no bare `except`; `_resolve_confidence` returns a number (never None); `apply_plan` raises typed errors only at boundary.
- **S7 Imports**: 3 groups (stdlib, third-party, local), alphabetised, absolute, no `import *`.
- **S8 Module size**: `apply_plan.py` is at 310 lines; with ~30 lines for sub-column routing it approaches 340. Decision: extract `_route_subfield_value` and `_resolve_confidence` to a sibling `apply_plan_helpers.py` only if the public file would exceed ~250 lines after restructuring. Decision deferred to implementation-plan phase based on actual diff.
- **S9 Test seams**: no test-only kwargs; new tests inject FakeLLM through constructor (existing pattern).

## What's preserved from current architecture

- ADR-0001 multi-agent split — agent set unchanged.
- ADR-0002 faithful extraction — verbatim cell values, no splitting, null+Warning over fabrication.
- ADR-0003 SheetRowPlanner invariants — `apply_plan` 100% deterministic, statically asserted; LLM as reviewer/namer.
- ADR-0004 five-tier test taxonomy — every change covered.
- ADR-0005 SigNoz telemetry — all metric names and trace shapes preserved.
- D1–D10 locked decisions — no reopens.
- Four extensibility axes — this change lives along axis B (artifact field additions), not C (new agent) or D (new tool).

---

**Author:** Claude (this brainstorming session)
**Reviewers:** Nagasai
**Implementation plan:** to be written next via `superpowers:writing-plans`.
