# Symmetric planner→agent contract — Phase 1 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `SheetPlan` so ROW_PER_PLI (via new `header_labels`) and SECTION_PER_PLI (via existing `pli_blocks[].identity`) feed `FieldNamer` and `apply_plan` the same way SHEET_IS_PLI's `kv_anchors` do. After Phase 1, every file in `dataset/` returns non-empty PLIs with populated canonical fields, real stages, and `extraction_confidence > 0.4`.

**Architecture:** Additive bridge-artifact extension. `SheetPlan` gains `header_labels: list[HeaderLabel]`. `StageBandSpec` gains `stage_columns: list[StageColumn]` (the resurrected, unused `StageColumn` type at artifacts.py:127 — populated with sub_columns for wide_sub_columns layouts). `KVAnchor` gains a default `confidence: float`. `CanonicalNameMap` gains optional `stage_subfield_labels`, `field_confidence`, `stage_confidence`. `apply_plan` writes per-field `PLI.confidence`. `FieldNamer._build_user_input` reads all three identity channels symmetrically and includes a small sample of values. New Tier 1 invariants enforce mode↔channel exclusivity.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, Haystack, openpyxl, Anthropic SDK, structlog, OpenTelemetry, pytest.

**Spec reference:** `docs/superpowers/specs/2026-05-19-symmetric-planner-agent-contract-design.md`.

**Coding standard:** Every file touched runs the §10 checklist of `docs/CODING_STANDARD.md` before commit. Function bodies ≤40 lines unless `# allow-long: <reason>`; modern type hints; absolute imports in three groups; no plan-task references in code or commits.

**Commit style:** Conventional commits per project convention. Do NOT reference plan-task numbers in commit bodies.

**Note on FA26 discovery:** During spec writing, `block_segmenter.py` was assumed to need an identity-fill change. Reading the actual code (block_segmenter.py:52-63) shows it already fills identity + stage_bands per block by bbox-filter. The real FA26 failure is upstream — likely mode-misclassification (SECTION_PER_PLI chosen for a tabular sheet that has no scattered KV labels). Phase 1 handles this by emitting a Warning on empty-identity blocks; root-cause mode-detection fix is deferred per the spec's "Open / deferred" list.

---

## File structure

**Modify:**
- `app/models/artifacts.py` — new types + new fields (Task 1)
- `app/services/planner/stage_band_detector.py` — populate `stage_columns`, wire sub_columns (Tasks 2, 3)
- `app/services/planner/block_segmenter.py` — Warning emission only (Task 4)
- `app/services/planner/plan.py` — `_collect_header_labels` + wiring (Task 5)
- `app/services/validation/plan_invariants.py` — two new invariants (Task 6)
- `app/services/applier/apply_plan.py` — header_labels read, sub_columns routing, confidence (Tasks 7, 8, 9, 10)
- `app/services/agents/field_namer.py` — mode-agnostic builder, value sampling (Tasks 11, 12)
- `app/prompts/workflow/field_namer.md` — expanded vocab (Task 13)

**Create:**
- `tests/unit/models/test_artifacts_new_shape.py`
- `tests/unit/planner/test_stage_band_detector_wide.py`
- `tests/unit/planner/test_block_segmenter_empty_block_warning.py`
- `tests/unit/planner/test_header_label_collector.py`
- `tests/unit/validation/test_plan_invariants_new.py`
- `tests/unit/applier/test_resolve_confidence.py`
- `tests/unit/applier/test_emit_single_row_pli_header_labels.py`
- `tests/unit/applier/test_read_wide_stage_column_sub_cols.py`
- `tests/agent/test_field_namer_row_per_pli_input.py`
- `tests/agent/test_field_namer_value_sampling.py`
- `tests/fixtures/builders/row_per_pli_wide_single_row_strip.py`
- `tests/fixtures/expected/row_per_pli_wide_single_row_strip.json`
- `tests/fixtures/builders/row_per_pli_wide_two_row_strip.py`
- `tests/fixtures/expected/row_per_pli_wide_two_row_strip.json`
- `tests/fixtures/builders/section_per_pli_blocks_with_identity.py`
- `tests/fixtures/expected/section_per_pli_blocks_with_identity.json`
- `tests/fixtures/builders/failure_segmenter_block_empty.py`
- `tests/fixtures/expected/failure_segmenter_block_empty.json`
- `tests/fixtures/builders/failure_multiple_identity_channels.py`
- `tests/fixtures/expected/failure_multiple_identity_channels.json`
- `tests/live/test_extract_live_regression.py`

**Touch (additive assertions only):**
- `tests/fixtures/expected/*.json` for existing ROW_PER_PLI scenarios — one-line `header_labels` count assertion (Task 16).

---

## Task 1: Add new schema fields to artifacts.py

**Files:**
- Modify: `app/models/artifacts.py`
- Test: `tests/unit/models/test_artifacts_new_shape.py`

**Context:** Six additive deltas, all defaulted, no removals. `StageColumn` already declared at artifacts.py:127 but unused by `SheetPlan`/`StageBandSpec` — we wire it in.

- [ ] **Step 1.1: Write the failing tests**

Create `tests/unit/models/test_artifacts_new_shape.py`:

```python
"""Shape-only tests for the new bridge-artifact fields added in Phase 1."""
from app.models.artifacts import (
    CanonicalNameMap,
    HeaderLabel,
    KVAnchor,
    SheetPlan,
    StageBandSpec,
    StageColumn,
)
from app.enums.pli_mode import PliMode


def test_header_label_validates() -> None:
    hl = HeaderLabel(raw="IO NO", col="B", row=3)
    assert hl.raw == "IO NO"
    assert hl.col == "B"
    assert hl.row == 3
    assert hl.confidence == 0.85


def test_stage_column_accepts_sub_columns() -> None:
    sc = StageColumn(
        name="CUTTING",
        name_cell="U3",
        primary_col="U",
        sub_columns={"Actual": "V", "Remarks": "W"},
    )
    assert sc.sub_columns["Actual"] == "V"


def test_kv_anchor_default_confidence() -> None:
    kv = KVAnchor(label_cell="A1", value_cell="B1", field="io_number")
    assert kv.confidence == 0.95


def test_stage_band_spec_default_stage_columns_empty() -> None:
    band = StageBandSpec(name="band", name_cell="A1", sub_header_row=2)
    assert band.stage_columns == []
    assert band.stage_cols == {}


def test_sheet_plan_default_header_labels_empty() -> None:
    plan = SheetPlan(sheet="S", pli_mode=PliMode.ROW_PER_PLI)
    assert plan.header_labels == []


def test_canonical_name_map_optional_confidence_dicts() -> None:
    nm = CanonicalNameMap()
    assert nm.field_confidence == {}
    assert nm.stage_confidence == {}
    assert nm.stage_subfield_labels == {}
```

- [ ] **Step 1.2: Run tests to verify they fail**

```
pytest tests/unit/models/test_artifacts_new_shape.py -v
```

Expected: 6 failures with `ImportError: cannot import name 'HeaderLabel'` and `AttributeError` for the missing fields.

- [ ] **Step 1.3: Add `HeaderLabel` class to artifacts.py**

Insert after the `WorkbookSummary` block (around line 35), before the `StructuralFingerprint` block:

```python
class HeaderLabel(BaseModel):
    """A column header label discovered in a sheet's header rows.

    Used for ROW_PER_PLI mode to surface raw column-header strings into
    the SheetPlan artifact, so FieldNamer can map them to canonical fields.
    """

    model_config = ConfigDict(extra="ignore")
    raw: str
    col: str
    row: int
    confidence: float = 0.85
```

- [ ] **Step 1.4: Add `confidence` field to `KVAnchor`**

Locate the `KVAnchor` class (around artifacts.py:223) and add:

```python
class KVAnchor(BaseModel):
    """A label→value cell pair extracted from a key-value region of a sheet."""

    model_config = ConfigDict(extra="ignore")
    label_cell: str
    value_cell: str
    field: str
    confidence: float = 0.95
```

- [ ] **Step 1.5: Add `stage_columns` field to `StageBandSpec`**

Locate `StageBandSpec` (around artifacts.py:232) and append:

```python
class StageBandSpec(BaseModel):
    """Where one stage band lives on a sheet.

    ``sub_rows`` keys are SubRowRole values (str); ``stage_cols`` maps a stage's
    display name to its column letter. ``stage_columns`` is the structured
    successor that also carries per-stage sub-columns for wide_sub_columns
    layouts; ``stage_cols`` is kept as a deprecated alias for one release.
    """

    model_config = ConfigDict(extra="ignore")
    name: str
    name_cell: str
    sub_header_row: int
    sub_rows: dict[str, int] = Field(default_factory=dict)
    stage_cols: dict[str, str] = Field(default_factory=dict)
    stage_columns: list[StageColumn] = Field(default_factory=list)
    layout_mode: str = "wide_sub_columns"
```

`StageColumn` already exists at artifacts.py:127 — reuse, do not redeclare. The forward reference works because Pydantic v2 resolves module-level names lazily.

- [ ] **Step 1.6: Add `header_labels` field to `SheetPlan`**

Locate `SheetPlan` (around artifacts.py:258) and append `header_labels`:

```python
class SheetPlan(BaseModel):
    """The planner's complete description of a sheet — header rows, row classifications, KV anchors, stage bands, PLI blocks, and pli_mode.

    ``rows`` is populated when pli_mode = ROW_PER_PLI.
    ``pli_blocks`` is populated when pli_mode = SECTION_PER_PLI.
    ``kv_anchors`` is populated when pli_mode = SHEET_IS_PLI (and also on hybrid
    sheets where workbook-header KV applies to every PLI emitted from ``rows``).
    ``header_labels`` is populated when pli_mode = ROW_PER_PLI — the identity
    channel for that mode.
    """

    model_config = ConfigDict(extra="ignore")
    sheet: str
    pli_mode: PliMode
    identity_column: str | None = None
    header_rows: list[int] = Field(default_factory=list)
    rows: list[RowSpec] = Field(default_factory=list)
    pli_blocks: list[PliBlock] = Field(default_factory=list)
    kv_anchors: list[KVAnchor] = Field(default_factory=list)
    header_labels: list[HeaderLabel] = Field(default_factory=list)
    stage_bands: list[StageBandSpec] = Field(default_factory=list)
    stage_scope: StageScope = StageScope.SHEET_LEVEL
    confidence: float = 1.0
```

- [ ] **Step 1.7: Add `stage_subfield_labels` + confidence dicts to `CanonicalNameMap`**

Locate `CanonicalNameMap` (around artifacts.py:280):

```python
class CanonicalNameMap(BaseModel):
    """FieldNamer's output — map detected labels to canonical field and stage names.

    Adds optional ``stage_subfield_labels`` for wide_sub_columns sub-columns,
    plus ``field_confidence`` / ``stage_confidence`` so the LLM can self-report
    per-label confidence. All four dicts default empty so existing FakeLLM canned
    responses validate without change.
    """

    model_config = ConfigDict(extra="ignore")
    field_labels: dict[str, str] = Field(default_factory=dict)
    stage_names: dict[str, str] = Field(default_factory=dict)
    stage_subfield_labels: dict[str, str] = Field(default_factory=dict)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    stage_confidence: dict[str, float] = Field(default_factory=dict)
```

- [ ] **Step 1.8: Run tests to verify they pass**

```
pytest tests/unit/models/test_artifacts_new_shape.py -v
```

Expected: 6 PASS.

- [ ] **Step 1.9: Run the full test suite to confirm no regressions**

```
pytest tests -q -m "not live"
```

Expected: same count as baseline (~209) + 6 new = ~215, all PASS.

- [ ] **Step 1.10: Commit**

```bash
git add app/models/artifacts.py tests/unit/models/test_artifacts_new_shape.py
git commit -m "feat(artifacts): symmetric SheetPlan contract — HeaderLabel, stage_columns, confidence"
```

---

## Task 2: stage_band_detector — populate `stage_columns` alongside `stage_cols`

**Files:**
- Modify: `app/services/planner/stage_band_detector.py`
- Test: `tests/unit/planner/test_stage_band_detector_wide.py`

**Context:** The detector currently emits `stage_cols: dict[str, str]`. This task adds parallel population of `stage_columns: list[StageColumn]` mirroring `stage_cols`, with empty `sub_columns` for now. Task 3 fills sub_columns.

- [ ] **Step 2.1: Write the failing test**

Create `tests/unit/planner/test_stage_band_detector_wide.py`:

```python
"""Stage-band detector — wide_sub_columns shape via stage_columns list."""
from datetime import date

from app.models.artifacts import SheetSignals
from app.repositories.workbook_repo import register_workbook
from app.services.planner.stage_band_detector import detect_stage_bands


def _signals(max_row: int, max_col: int) -> SheetSignals:
    return SheetSignals(sheet="S", max_row=max_row, max_col=max_col)


def test_wide_band_emits_stage_columns_list(tmp_path) -> None:
    """Detector populates stage_columns mirroring stage_cols (empty sub_columns)."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A3"] = "S NO"
    ws["B3"] = "IO"
    ws["U3"] = "CUTTING"
    ws["V3"] = "SEWING"
    ws["U4"] = date(2026, 3, 12)
    ws["V4"] = date(2026, 4, 3)
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ctx = register_workbook(p)

    bands = detect_stage_bands(ctx, "S", _signals(max_row=4, max_col=22))
    assert len(bands) == 1
    b = bands[0]
    assert b.layout_mode == "wide_sub_columns"
    assert b.stage_cols == {"CUTTING": "U", "SEWING": "V"}
    assert len(b.stage_columns) == 2
    by_name = {sc.name: sc for sc in b.stage_columns}
    assert by_name["CUTTING"].primary_col == "U"
    assert by_name["CUTTING"].name_cell == "U3"
    assert by_name["CUTTING"].sub_columns == {}
    assert by_name["SEWING"].primary_col == "V"
```

- [ ] **Step 2.2: Run test to verify it fails**

```
pytest tests/unit/planner/test_stage_band_detector_wide.py -v
```

Expected: FAIL with `AssertionError: assert [] == ... (stage_columns empty)`.

- [ ] **Step 2.3: Add a helper to build `StageColumn` entries**

Edit `app/services/planner/stage_band_detector.py`. Add an import at the top of the file (in the local-import group):

```python
from app.models.artifacts import SheetSignals, StageBandSpec, StageColumn
```

Insert a helper above `detect_stage_bands`:

```python
def _build_stage_columns(
    stage_cols: dict[str, str], sub_header_row: int,
) -> list[StageColumn]:
    """Build a StageColumn per (stage_name, col) pair with empty sub_columns.

    Phase 1 step 1: structural-only mirror of `stage_cols`. Sub-columns are
    filled by `_collect_sub_columns` in the wide_sub_columns code path.
    """
    return [
        StageColumn(
            name=name,
            name_cell=f"{col_letter}{sub_header_row}",
            primary_col=col_letter,
        )
        for name, col_letter in stage_cols.items()
    ]
```

- [ ] **Step 2.4: Wire `stage_columns` into the band emission**

In `detect_stage_bands`, locate the `bands.append(StageBandSpec(...))` call (around stage_band_detector.py:148). Replace with:

```python
bands.append(StageBandSpec(
    name=section_title,
    name_cell=name_cell,
    sub_header_row=sub_header_row,
    sub_rows=sub_rows,
    stage_cols=stage_cols,
    stage_columns=_build_stage_columns(stage_cols, sub_header_row),
    layout_mode=layout_mode,
))
```

- [ ] **Step 2.5: Run test to verify it passes**

```
pytest tests/unit/planner/test_stage_band_detector_wide.py -v
```

Expected: PASS.

- [ ] **Step 2.6: Run the full test suite**

```
pytest tests -q -m "not live"
```

Expected: all PASS, no regressions in existing tall_sub_rows fixtures.

- [ ] **Step 2.7: Commit**

```bash
git add app/services/planner/stage_band_detector.py tests/unit/planner/test_stage_band_detector_wide.py
git commit -m "feat(planner): emit stage_columns mirror of stage_cols"
```

---

## Task 3: stage_band_detector — fill `sub_columns` for wide_sub_columns

**Files:**
- Modify: `app/services/planner/stage_band_detector.py`
- Test: extend `tests/unit/planner/test_stage_band_detector_wide.py`

**Context:** For `wide_sub_columns` layout, the row beneath each stage cell may carry sub-field labels (Plan/Actual/Remarks/Qty). This task scans that row for each stage's `primary_col` neighbours and populates `sub_columns`.

- [ ] **Step 3.1: Write the failing test (extension)**

Append to `tests/unit/planner/test_stage_band_detector_wide.py`:

```python
def test_wide_band_fills_sub_columns_from_row_below(tmp_path) -> None:
    """When row below stage name has labels, they populate sub_columns."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    # Row 3 = stage names, Row 4 = sub-field names, Row 5 = data row with dates
    ws["U3"] = "CUTTING"
    ws["V3"] = None  # no second-stage-name; V belongs under CUTTING
    ws["U4"] = "Plan"
    ws["V4"] = "Actual"
    ws["U5"] = date(2026, 3, 12)
    ws["V5"] = date(2026, 3, 16)
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ctx = register_workbook(p)

    bands = detect_stage_bands(ctx, "S", _signals(max_row=5, max_col=22))
    # The detector seeds bands from rows with ≥2 date cells; row 5 qualifies.
    # The header row above (row 4) holds the immediate sub-headers; row 3 holds
    # the stage name "CUTTING" with V3 empty (shared stage span).
    assert any(b.layout_mode == "wide_sub_columns" for b in bands)
    band = next(b for b in bands if b.layout_mode == "wide_sub_columns")
    by_name = {sc.name: sc for sc in band.stage_columns}
    assert "CUTTING" in by_name
    # Sub-column "Actual" should be on CUTTING with V col.
    assert by_name["CUTTING"].sub_columns.get("Actual") == "V"
```

- [ ] **Step 3.2: Run test to verify it fails**

```
pytest tests/unit/planner/test_stage_band_detector_wide.py::test_wide_band_fills_sub_columns_from_row_below -v
```

Expected: FAIL with `assert by_name["CUTTING"].sub_columns.get("Actual") == "V"` — sub_columns is empty.

- [ ] **Step 3.3: Add sub_columns collection helper**

Add to `stage_band_detector.py`, above `_build_stage_columns`:

```python
def _collect_sub_columns(
    ws: object, stage_name_row: int, sub_label_row: int, max_col: int,
    stage_cols: dict[str, str],
) -> dict[str, dict[str, str]]:
    """Map each stage to its sub-column labels read from `sub_label_row`.

    For each adjacent column after a stage's primary column, if the cell at
    (sub_label_row, col) is a non-stage-vocab string, attribute it to the nearest
    preceding stage. Returns {stage_name: {sub_label: col_letter}}.
    """
    if sub_label_row == stage_name_row:
        return {name: {} for name in stage_cols}

    primary_cols_by_idx = {
        column_index_from_string(col): name for name, col in stage_cols.items()
    }
    sorted_idx = sorted(primary_cols_by_idx)
    result: dict[str, dict[str, str]] = {name: {} for name in stage_cols}

    for c in range(1, max_col + 1):
        if c in primary_cols_by_idx:
            continue
        preceding = [i for i in sorted_idx if i < c]
        if not preceding:
            continue
        owner_stage = primary_cols_by_idx[preceding[-1]]
        # Stop attributing to a stage once we cross the next stage's column.
        following = [i for i in sorted_idx if i > preceding[-1]]
        if following and c >= following[0]:
            continue
        v = ws.cell(row=sub_label_row, column=c).value
        if isinstance(v, str) and v.strip():
            result[owner_stage][v.strip()] = get_column_letter(c)

    return result
```

Add the `column_index_from_string` import at the top:

```python
from openpyxl.utils import column_index_from_string, get_column_letter
```

- [ ] **Step 3.4: Wire sub_columns into `_build_stage_columns`**

Replace `_build_stage_columns` and update the call site to pass sub-column data:

```python
def _build_stage_columns(
    stage_cols: dict[str, str], sub_header_row: int,
    sub_columns_by_stage: dict[str, dict[str, str]] | None = None,
) -> list[StageColumn]:
    """Build a StageColumn per (stage_name, col) pair, with sub_columns when known."""
    sub_columns_by_stage = sub_columns_by_stage or {}
    return [
        StageColumn(
            name=name,
            name_cell=f"{col_letter}{sub_header_row}",
            primary_col=col_letter,
            sub_columns=sub_columns_by_stage.get(name, {}),
        )
        for name, col_letter in stage_cols.items()
    ]
```

In `detect_stage_bands`, replace the `bands.append(...)` call from Task 2 with:

```python
sub_columns_by_stage: dict[str, dict[str, str]] = {}
if layout_mode == "wide_sub_columns":
    sub_label_row = sub_header_row + 1
    if sub_label_row <= signals.max_row:
        sub_columns_by_stage = _collect_sub_columns(
            ws, stage_name_row=sub_header_row,
            sub_label_row=sub_label_row, max_col=signals.max_col,
            stage_cols=stage_cols,
        )

bands.append(StageBandSpec(
    name=section_title,
    name_cell=name_cell,
    sub_header_row=sub_header_row,
    sub_rows=sub_rows,
    stage_cols=stage_cols,
    stage_columns=_build_stage_columns(
        stage_cols, sub_header_row, sub_columns_by_stage
    ),
    layout_mode=layout_mode,
))
```

- [ ] **Step 3.5: Run test to verify it passes**

```
pytest tests/unit/planner/test_stage_band_detector_wide.py -v
```

Expected: both tests PASS.

- [ ] **Step 3.6: Run the full test suite**

```
pytest tests -q -m "not live"
```

Expected: all PASS; no regression in tall_sub_rows fixtures (they have `sub_columns_by_stage={}` so `sub_columns` stays empty for tall mode).

- [ ] **Step 3.7: Commit**

```bash
git add app/services/planner/stage_band_detector.py tests/unit/planner/test_stage_band_detector_wide.py
git commit -m "feat(planner): fill sub_columns for wide_sub_columns stage bands"
```

---

## Task 4: block_segmenter — emit Warning for empty-identity blocks

**Files:**
- Modify: `app/services/planner/block_segmenter.py`
- Test: `tests/unit/planner/test_block_segmenter_empty_block_warning.py`

**Context:** `segment_blocks` already correctly fills `block.identity` and `block.stage_bands` by bbox filter (block_segmenter.py:52-63). What it doesn't do is signal when a block has empty identity (the FA26 failure mode). Spec section 5.1 calls for emitting a Warning. Since `segment_blocks` returns blocks and doesn't have access to a Warning channel, we emit a structured log event with `event="block_empty_identity"` so it surfaces via SigNoz, and add a Tier 2 statistic that becomes a `ValidationFinding` later.

- [ ] **Step 4.1: Write the failing test**

Create `tests/unit/planner/test_block_segmenter_empty_block_warning.py`:

```python
"""block_segmenter logs an event when a PliBlock has no identity anchors."""
import structlog
from app.enums.row_role import RowRole
from app.models.artifacts import RowSpec
from app.services.planner.block_segmenter import segment_blocks


def test_empty_block_emits_log_event(caplog) -> None:
    rows = [
        RowSpec(idx=2, role=RowRole.ANCHOR),
        RowSpec(idx=5, role=RowRole.ANCHOR),
    ]
    structlog.reset_defaults()  # use stdlib logging path for caplog capture
    blocks = segment_blocks(rows=rows, kv_anchors=[], blank_run_gaps=[], stage_bands=[])
    assert len(blocks) == 2
    assert all(b.identity == [] for b in blocks)
    msgs = [r.message for r in caplog.records if "block_empty_identity" in r.message]
    # 2 blocks, 2 events.
    assert len(msgs) == 2
```

- [ ] **Step 4.2: Run test to verify it fails**

```
pytest tests/unit/planner/test_block_segmenter_empty_block_warning.py -v
```

Expected: FAIL `assert len(msgs) == 2` (msgs is empty).

- [ ] **Step 4.3: Emit log event for empty-identity blocks**

In `app/services/planner/block_segmenter.py`, after the `blocks.append(...)` line and before `block_id += 1`, add:

```python
        if not block_kvs:
            log.warning(
                "block_empty_identity",
                block_id=block_id,
                bbox_start=start,
                bbox_end=end,
            )
```

The Tier 2 validator that converts this into a `ValidationFinding` lands in Task 6.

- [ ] **Step 4.4: Run test to verify it passes**

```
pytest tests/unit/planner/test_block_segmenter_empty_block_warning.py -v
```

Expected: PASS.

- [ ] **Step 4.5: Commit**

```bash
git add app/services/planner/block_segmenter.py tests/unit/planner/test_block_segmenter_empty_block_warning.py
git commit -m "feat(planner): log block_empty_identity event for traceability"
```

---

## Task 5: plan.py — `_collect_header_labels` + wiring

**Files:**
- Modify: `app/services/planner/plan.py`
- Test: `tests/unit/planner/test_header_label_collector.py`

**Context:** After `detect_stage_bands` runs, walk every column not claimed by a stage band's `primary_col` or `sub_columns` and harvest the first non-empty string from `plan.header_rows`. Populates `plan.header_labels` for ROW_PER_PLI; empty for other modes.

- [ ] **Step 5.1: Write the failing test**

Create `tests/unit/planner/test_header_label_collector.py`:

```python
"""_collect_header_labels — populates header_labels for ROW_PER_PLI, skips claimed cols."""
import openpyxl
from app.enums.pli_mode import PliMode
from app.models.artifacts import HeaderLabel, SheetPlan, StageBandSpec, StageColumn
from app.services.planner.plan import _collect_header_labels


def _ws_with_header(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    # Row 3 header row
    ws["B3"] = "IO NO"
    ws["F3"] = "STYLE"
    ws["K3"] = "COLOR"
    ws["U3"] = "CUTTING"   # claimed by stage band
    ws["V3"] = "Actual"    # claimed sub-col
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    return openpyxl.load_workbook(p)["S"]


def test_collects_identity_columns_skipping_stage_cols(tmp_path) -> None:
    ws = _ws_with_header(tmp_path)
    band = StageBandSpec(
        name="b", name_cell="U3", sub_header_row=3,
        stage_columns=[StageColumn(name="CUTTING", name_cell="U3", primary_col="U",
                                    sub_columns={"Actual": "V"})],
    )
    plan = SheetPlan(sheet="S", pli_mode=PliMode.ROW_PER_PLI,
                     header_rows=[3], stage_bands=[band])
    labels = _collect_header_labels(ws, plan)
    raws = sorted(hl.raw for hl in labels)
    assert raws == ["COLOR", "IO NO", "STYLE"]
    assert all(isinstance(hl, HeaderLabel) for hl in labels)
    by_raw = {hl.raw: hl for hl in labels}
    assert by_raw["IO NO"].col == "B"
    assert by_raw["IO NO"].row == 3


def test_returns_empty_for_non_row_per_pli(tmp_path) -> None:
    ws = _ws_with_header(tmp_path)
    plan = SheetPlan(sheet="S", pli_mode=PliMode.SHEET_IS_PLI, header_rows=[3])
    assert _collect_header_labels(ws, plan) == []
    plan2 = SheetPlan(sheet="S", pli_mode=PliMode.SECTION_PER_PLI, header_rows=[3])
    assert _collect_header_labels(ws, plan2) == []
```

- [ ] **Step 5.2: Run tests to verify they fail**

```
pytest tests/unit/planner/test_header_label_collector.py -v
```

Expected: FAIL with `ImportError: cannot import name '_collect_header_labels'`.

- [ ] **Step 5.3: Add `_collect_header_labels` to plan.py**

Edit `app/services/planner/plan.py`. Add the import (in the third-party group, alongside `get_column_letter`):

```python
from openpyxl.utils import get_column_letter
```

Already imported — just confirm. Add `HeaderLabel` to the local imports block:

```python
from app.models.artifacts import (
    HeaderLabel,
    KVAnchor,
    PliBlock,
    SheetPlan,
    SheetSignals,
    StageBandSpec,
    RowSpec,
)
```

Add the helper above `class SheetRowPlanner:` (around plan.py:158):

```python
def _collect_header_labels(ws: object, plan: SheetPlan) -> list[HeaderLabel]:
    """Lift identity-column header strings from header_rows into the artifact.

    For each column NOT claimed by a stage band's primary_col or sub_columns,
    take the first non-empty string scanning header_rows top-to-bottom. Returns
    empty for non-ROW_PER_PLI modes.
    """
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

- [ ] **Step 5.4: Wire `_collect_header_labels` into `SheetRowPlanner.run`**

In `SheetRowPlanner.run` (around plan.py:163), after `header_rows = [...]` and before `blocks, stage_bands_sheet, stage_scope = ...`, build the plan in two steps: first a draft to know stage bands, then populate header_labels.

Replace the plan construction (around plan.py:185-200) with:

```python
        plan = SheetPlan(
            sheet=sheet,
            pli_mode=pli_mode,
            identity_column=identity_column,
            header_rows=header_rows,
            rows=rows,
            pli_blocks=blocks,
            kv_anchors=kv_anchors if pli_mode is PliMode.SHEET_IS_PLI else [],
            stage_bands=stage_bands_sheet,
            stage_scope=stage_scope,
            confidence=_compute_confidence(pli_mode, kv_anchors),
        )
        ws = workbook_ctx.wb[sheet]
        plan = plan.model_copy(update={"header_labels": _collect_header_labels(ws, plan)})
        log.info("planner_complete", sheet=sheet, pli_mode=plan.pli_mode.value,
                 rows=len(plan.rows), blocks=len(plan.pli_blocks),
                 kv=len(plan.kv_anchors), header_labels=len(plan.header_labels),
                 bands=len(plan.stage_bands),
                 confidence=plan.confidence)
        return {"plan": plan}
```

- [ ] **Step 5.5: Run the test to verify it passes**

```
pytest tests/unit/planner/test_header_label_collector.py -v
```

Expected: both PASS.

- [ ] **Step 5.6: Run the full test suite**

```
pytest tests -q -m "not live"
```

Expected: all PASS; existing fixtures for ROW_PER_PLI may now have `header_labels` populated but no assertion on them yet (Task 16 handles that).

- [ ] **Step 5.7: Commit**

```bash
git add app/services/planner/plan.py tests/unit/planner/test_header_label_collector.py
git commit -m "feat(planner): collect header_labels for ROW_PER_PLI sheets"
```

---

## Task 6: New Tier 1 invariants — channel exclusivity + mode consistency

**Files:**
- Modify: `app/services/validation/plan_invariants.py`
- Test: `tests/unit/validation/test_plan_invariants_new.py`

**Context:** Two ERROR-level checks: exactly one identity channel populated; channel matches `pli_mode`.

- [ ] **Step 6.1: Write the failing tests**

Create `tests/unit/validation/test_plan_invariants_new.py`:

```python
"""Tier 1 invariants: exactly_one_identity_channel + mode_channel_consistency."""
from app.enums.pli_mode import PliMode
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import (
    HeaderLabel,
    KVAnchor,
    PliBlock,
    SheetPlan,
)
from app.services.validation.plan_invariants import validate_invariants


def test_row_per_pli_with_header_labels_passes_invariants() -> None:
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_labels=[HeaderLabel(raw="IO", col="B", row=3)],
    )
    findings = validate_invariants(plan)
    error_checks = {f.check for f in findings if f.severity == ValidationSeverity.ERROR}
    assert "exactly_one_identity_channel" not in error_checks
    assert "mode_channel_consistency" not in error_checks


def test_two_channels_populated_fires_error() -> None:
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_labels=[HeaderLabel(raw="IO", col="B", row=3)],
        kv_anchors=[KVAnchor(label_cell="A1", value_cell="B1", field="io")],
    )
    findings = validate_invariants(plan)
    assert any(
        f.check == "exactly_one_identity_channel" and f.severity == ValidationSeverity.ERROR
        for f in findings
    )


def test_mode_channel_mismatch_fires_error() -> None:
    """SHEET_IS_PLI but header_labels populated instead of kv_anchors."""
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.SHEET_IS_PLI,
        header_labels=[HeaderLabel(raw="IO", col="B", row=3)],
    )
    findings = validate_invariants(plan)
    assert any(
        f.check == "mode_channel_consistency" and f.severity == ValidationSeverity.ERROR
        for f in findings
    )


def test_no_channel_populated_is_not_an_error() -> None:
    """An empty plan is allowed during planner bring-up (caught by other validators)."""
    plan = SheetPlan(sheet="S", pli_mode=PliMode.ROW_PER_PLI)
    findings = validate_invariants(plan)
    error_checks = {f.check for f in findings if f.severity == ValidationSeverity.ERROR}
    assert "exactly_one_identity_channel" not in error_checks
```

- [ ] **Step 6.2: Run tests to verify they fail**

```
pytest tests/unit/validation/test_plan_invariants_new.py -v
```

Expected: FAILs — the new check names aren't emitted yet.

- [ ] **Step 6.3: Add the two invariant checks to plan_invariants.py**

Edit `app/services/validation/plan_invariants.py`. Add the import for `PliMode`:

```python
from app.enums.pli_mode import PliMode
```

Insert two new check functions above `validate_invariants`:

```python
def _check_exactly_one_identity_channel(plan: SheetPlan) -> list[ValidationFinding]:
    """Exactly one of header_labels / kv_anchors / pli_blocks may be non-empty."""
    populated = [
        ("header_labels", bool(plan.header_labels)),
        ("kv_anchors", bool(plan.kv_anchors)),
        ("pli_blocks", bool(plan.pli_blocks)),
    ]
    count = sum(1 for _, v in populated if v)
    if count > 1:
        names = ", ".join(n for n, v in populated if v)
        return [_error(
            "exactly_one_identity_channel",
            f"multiple identity channels populated: {names}",
        )]
    return []


def _check_mode_channel_consistency(plan: SheetPlan) -> list[ValidationFinding]:
    """pli_mode must match the populated identity channel."""
    expected = {
        PliMode.ROW_PER_PLI: bool(plan.header_labels),
        PliMode.SHEET_IS_PLI: bool(plan.kv_anchors),
        PliMode.SECTION_PER_PLI: bool(plan.pli_blocks),
    }
    any_populated = bool(plan.header_labels or plan.kv_anchors or plan.pli_blocks)
    if not any_populated:
        return []  # empty plan — handled elsewhere
    if not expected.get(plan.pli_mode, False):
        return [_error(
            "mode_channel_consistency",
            f"pli_mode={plan.pli_mode.value} but its expected channel is empty",
        )]
    return []
```

Append both to the `validate_invariants` call list:

```python
def validate_invariants(plan: SheetPlan) -> list[ValidationFinding]:
    """Run all Tier 1 structural invariant checks against a SheetPlan."""
    findings = [
        *_check_reference_integrity(plan),
        *_check_row_uniqueness(plan),
        *_check_header_contiguity(plan),
        *_check_pli_blocks_disjoint(plan),
        *_check_sub_row_consistency(plan),
        *_check_exactly_one_identity_channel(plan),
        *_check_mode_channel_consistency(plan),
    ]
    ...
```

- [ ] **Step 6.4: Run tests to verify they pass**

```
pytest tests/unit/validation/test_plan_invariants_new.py -v
```

Expected: 4 PASS.

- [ ] **Step 6.5: Run the full test suite**

```
pytest tests -q -m "not live"
```

Expected: existing tests still PASS. Tier 1 errors may now fire on previously-quiet fixtures — these are real (channel population mismatches that existed silently). If any existing test fails, inspect, fix the fixture to align with the channel matrix, then re-run.

- [ ] **Step 6.6: Commit**

```bash
git add app/services/validation/plan_invariants.py tests/unit/validation/test_plan_invariants_new.py
git commit -m "feat(validation): tier-1 invariants for identity-channel exclusivity"
```

---

## Task 7: apply_plan — `_resolve_confidence` helper

**Files:**
- Modify: `app/services/applier/apply_plan.py`
- Test: `tests/unit/applier/test_resolve_confidence.py`

**Context:** Pure helper. LLM-supplied per-field confidence wins; otherwise return a source-type default. Calibration seed from spec §4.3 §C.

- [ ] **Step 7.1: Write the failing test**

Create `tests/unit/applier/test_resolve_confidence.py`:

```python
"""apply_plan._resolve_confidence — picks per-field confidence with calibrated defaults."""
from app.models.artifacts import CanonicalNameMap
from app.services.applier.apply_plan import _resolve_confidence


def test_llm_supplied_confidence_wins() -> None:
    nm = CanonicalNameMap(field_confidence={"io_number": 0.99})
    assert _resolve_confidence(source="header_label", name_map=nm,
                                raw="IO NO", canonical="io_number") == 0.99


def test_kv_anchor_default() -> None:
    nm = CanonicalNameMap()
    assert _resolve_confidence(source="kv_anchor", name_map=nm,
                                raw="IO", canonical="io_number") == 0.95


def test_header_label_default() -> None:
    nm = CanonicalNameMap()
    assert _resolve_confidence(source="header_label", name_map=nm,
                                raw="IO NO", canonical="io_number") == 0.85


def test_stage_subfield_default() -> None:
    nm = CanonicalNameMap()
    assert _resolve_confidence(source="stage_subfield", name_map=nm,
                                raw="Actual", canonical="actual_date") == 0.80


def test_metadata_fallback_default() -> None:
    nm = CanonicalNameMap()
    assert _resolve_confidence(source="metadata_fallback", name_map=nm,
                                raw="Unknown", canonical="Unknown") == 0.40


def test_unknown_source_default() -> None:
    nm = CanonicalNameMap()
    assert _resolve_confidence(source="other", name_map=nm, raw="x", canonical="x") == 0.5
```

- [ ] **Step 7.2: Run tests to verify they fail**

```
pytest tests/unit/applier/test_resolve_confidence.py -v
```

Expected: FAIL — `_resolve_confidence` does not exist.

- [ ] **Step 7.3: Add `_resolve_confidence` to apply_plan.py**

Edit `app/services/applier/apply_plan.py`. Add a constant table near the top after `_STRING_FIELDS`:

```python
_CONFIDENCE_DEFAULTS = {
    "kv_anchor": 0.95,
    "header_label": 0.85,
    "stage_column": 0.85,
    "stage_subfield": 0.80,
    "metadata_fallback": 0.40,
}
```

Add the helper above `_coerce`:

```python
def _resolve_confidence(*, source: str, name_map: CanonicalNameMap,
                        raw: str, canonical: str) -> float:
    """Pick a per-field confidence value.

    LLM-supplied confidence wins when the canonical name appears in
    `name_map.field_confidence`. Otherwise returns a calibrated default per
    source type. Returns 0.5 for unknown sources.
    """
    if canonical in name_map.field_confidence:
        return name_map.field_confidence[canonical]
    return _CONFIDENCE_DEFAULTS.get(source, 0.5)
```

- [ ] **Step 7.4: Run tests to verify they pass**

```
pytest tests/unit/applier/test_resolve_confidence.py -v
```

Expected: 6 PASS.

- [ ] **Step 7.5: Confirm static-analysis test still passes**

```
pytest tests/unit/applier/test_apply_plan_no_llm_imports.py -v
```

Expected: PASS — no new agent or llm_provider imports.

- [ ] **Step 7.6: Commit**

```bash
git add app/services/applier/apply_plan.py tests/unit/applier/test_resolve_confidence.py
git commit -m "feat(applier): _resolve_confidence helper with calibrated defaults"
```

---

## Task 8: apply_plan — `_emit_single_row_pli` reads from `plan.header_labels`

**Files:**
- Modify: `app/services/applier/apply_plan.py`
- Test: `tests/unit/applier/test_emit_single_row_pli_header_labels.py`

**Context:** Today `_emit_single_row_pli` re-reads `header_rows` cells to build `header_label_by_col`. With Task 5, the planner already did that work into `plan.header_labels`. Use it directly. No behavior change — same cell read, same PLI shape.

- [ ] **Step 8.1: Write the failing test**

Create `tests/unit/applier/test_emit_single_row_pli_header_labels.py`:

```python
"""_emit_single_row_pli reads from plan.header_labels (not re-scanning header_rows)."""
import openpyxl
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.models.artifacts import (
    CanonicalNameMap, HeaderLabel, RowSpec, SheetPlan, StageBandSpec, StageColumn,
)
from app.repositories.workbook_repo import register_workbook
from app.services.applier.apply_plan import apply_plan


def test_canonical_field_via_header_label(tmp_path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["B3"] = "IO NO"
    ws["B4"] = "1063"
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ctx = register_workbook(p)
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_rows=[3],
        rows=[RowSpec(idx=4, role=RowRole.ANCHOR)],
        header_labels=[HeaderLabel(raw="IO NO", col="B", row=3)],
    )
    name_map = CanonicalNameMap(field_labels={"IO NO": "io_number"})
    plis = apply_plan(ctx, plan, name_map)
    assert len(plis) == 1
    assert plis[0].io_number == "1063"
    # Confidence populated
    assert plis[0].confidence.get("io_number") == 0.85


def test_unknown_label_routes_to_metadata(tmp_path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["C3"] = "BUYER PO"
    ws["C4"] = "PO-00045"
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ctx = register_workbook(p)
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_rows=[3],
        rows=[RowSpec(idx=4, role=RowRole.ANCHOR)],
        header_labels=[HeaderLabel(raw="BUYER PO", col="C", row=3)],
    )
    name_map = CanonicalNameMap()  # empty → fall back to raw label
    plis = apply_plan(ctx, plan, name_map)
    assert plis[0].metadata.get("BUYER PO") == "PO-00045"
```

- [ ] **Step 8.2: Run tests to verify they fail**

```
pytest tests/unit/applier/test_emit_single_row_pli_header_labels.py -v
```

Expected: at least one test FAILs — `_emit_single_row_pli` may still ignore `plan.header_labels` and re-read cells, or confidence may not populate.

- [ ] **Step 8.3: Update `_emit_single_row_pli` to use `plan.header_labels`**

In `app/services/applier/apply_plan.py`, replace `_emit_single_row_pli` (apply_plan.py:169-195) with:

```python
def _emit_single_row_pli(ws, plan: SheetPlan, row: RowSpec,
                         header_label_by_col: dict[int, str],
                         name_map: CanonicalNameMap) -> PLI:
    """Build one PLI from a single data row plus plan-level KV anchors and stages.

    Identity columns come from `plan.header_labels` for ROW_PER_PLI; the legacy
    `header_label_by_col` parameter is kept as a fallback for fixtures that pre-date
    header_labels surfacing (Task 16 migrates them).
    """
    values: dict = {"metadata": {}, "confidence": {}}
    source_cells: dict[str, str] = {}

    iter_labels = (
        [(column_index_from_string(hl.col), hl.raw, "header_label") for hl in plan.header_labels]
        if plan.header_labels
        else [(c, lab, "header_label") for c, lab in header_label_by_col.items()]
    )

    for col_idx, label, source_kind in iter_labels:
        canonical = name_map.field_labels.get(label, label)
        if canonical == "ignore":
            continue
        val, addr = _read_with_merge(ws, row.idx, col_idx)
        if val is None:
            continue
        is_canonical_field = canonical in PLI.model_fields
        target_source = source_kind if is_canonical_field else "metadata_fallback"
        if is_canonical_field:
            values[canonical] = _coerce(canonical, val)
        else:
            values["metadata"][canonical] = val
        source_cells[canonical] = addr
        values["confidence"][canonical] = _resolve_confidence(
            source=target_source, name_map=name_map,
            raw=label, canonical=canonical,
        )

    for kv in plan.kv_anchors:
        _read_kv_into(values, source_cells, ws, kv, name_map)

    values["source"] = {"sheet": plan.sheet, "rows": [row.idx], "cells": source_cells}
    values["stages"] = _read_stages(ws, plan.stage_bands, row.idx, name_map, source_cells)
    return PLI(**values)
```

Also update `_read_kv_into` to record confidence (apply_plan.py:69-86):

```python
def _read_kv_into(values: dict, source_cells: dict, ws, kv: KVAnchor,
                  name_map: CanonicalNameMap) -> None:
    """Read one KV anchor cell and write the result into `values` and `source_cells`."""
    canonical = name_map.field_labels.get(kv.field, kv.field)
    if canonical == "ignore":
        return
    col_letter, row = coordinate_from_string(kv.value_cell)
    col = column_index_from_string(col_letter)
    val = ws.cell(row=row, column=col).value
    if val is None:
        return
    is_canonical_field = canonical in PLI.model_fields
    target_source = "kv_anchor" if is_canonical_field else "metadata_fallback"
    if is_canonical_field:
        values[canonical] = _coerce(canonical, val)
    else:
        values.setdefault("metadata", {})[canonical] = val
    source_cells[canonical] = kv.value_cell
    values.setdefault("confidence", {})[canonical] = _resolve_confidence(
        source=target_source, name_map=name_map,
        raw=kv.field, canonical=canonical,
    )
```

- [ ] **Step 8.4: Run tests to verify they pass**

```
pytest tests/unit/applier/test_emit_single_row_pli_header_labels.py -v
```

Expected: 2 PASS.

- [ ] **Step 8.5: Run the full test suite**

```
pytest tests -q -m "not live"
```

Expected: all PASS. The existing ROW_PER_PLI fixtures still extract because the legacy `header_label_by_col` fallback fires when `plan.header_labels` is empty (transitional period).

- [ ] **Step 8.6: Commit**

```bash
git add app/services/applier/apply_plan.py tests/unit/applier/test_emit_single_row_pli_header_labels.py
git commit -m "feat(applier): read identity labels from plan.header_labels"
```

---

## Task 9: apply_plan — `_read_wide_stage_column` reads `sub_columns`

**Files:**
- Modify: `app/services/applier/apply_plan.py`
- Test: `tests/unit/applier/test_read_wide_stage_column_sub_cols.py`

**Context:** Update the wide-mode resolver to iterate `stage_col.sub_columns`, canonicalising each via `name_map.stage_subfield_labels`. Canonical Stage fields write to Stage directly; everything else into `Stage.metadata`.

- [ ] **Step 9.1: Write the failing test**

Create `tests/unit/applier/test_read_wide_stage_column_sub_cols.py`:

```python
"""_read_wide_stage_column iterates sub_columns and routes them correctly."""
from datetime import date
import openpyxl
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.models.artifacts import (
    CanonicalNameMap, HeaderLabel, RowSpec, SheetPlan, StageBandSpec, StageColumn,
)
from app.repositories.workbook_repo import register_workbook
from app.services.applier.apply_plan import apply_plan


def test_sub_column_routes_to_stage_metadata(tmp_path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["U3"] = "CUTTING"
    ws["V3"] = "Actual"
    ws["U4"] = date(2026, 3, 12)
    ws["V4"] = date(2026, 3, 16)
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ctx = register_workbook(p)
    band = StageBandSpec(
        name="b", name_cell="U3", sub_header_row=3,
        sub_rows={"plan": 4},
        layout_mode="wide_sub_columns",
        stage_columns=[
            StageColumn(name="CUTTING", name_cell="U3", primary_col="U",
                         sub_columns={"Actual": "V"}),
        ],
    )
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_rows=[3], stage_bands=[band],
        rows=[RowSpec(idx=4, role=RowRole.ANCHOR)],
        header_labels=[HeaderLabel(raw="x", col="A", row=3)],  # to satisfy invariant
    )
    name_map = CanonicalNameMap(
        stage_names={"CUTTING": "cutting"},
        stage_subfield_labels={"Actual": "actual_date"},
    )
    plis = apply_plan(ctx, plan, name_map)
    assert len(plis) == 1
    assert len(plis[0].stages) == 1
    stage = plis[0].stages[0]
    assert stage.name == "cutting"
    assert stage.planned_date == date(2026, 3, 12)
    assert stage.metadata.get("actual_date") == date(2026, 3, 16)


def test_ignore_sentinel_skips_sub_column(tmp_path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["U3"] = "CUTTING"
    ws["V3"] = "Remarks"
    ws["U4"] = date(2026, 3, 12)
    ws["V4"] = "n/a"
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ctx = register_workbook(p)
    band = StageBandSpec(
        name="b", name_cell="U3", sub_header_row=3,
        sub_rows={"plan": 4},
        layout_mode="wide_sub_columns",
        stage_columns=[
            StageColumn(name="CUTTING", name_cell="U3", primary_col="U",
                         sub_columns={"Remarks": "V"}),
        ],
    )
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_rows=[3], stage_bands=[band],
        rows=[RowSpec(idx=4, role=RowRole.ANCHOR)],
        header_labels=[HeaderLabel(raw="x", col="A", row=3)],
    )
    name_map = CanonicalNameMap(
        stage_names={"CUTTING": "cutting"},
        stage_subfield_labels={"Remarks": "ignore"},
    )
    plis = apply_plan(ctx, plan, name_map)
    stage = plis[0].stages[0]
    assert "Remarks" not in stage.metadata
    assert "remarks" not in stage.metadata
```

- [ ] **Step 9.2: Run tests to verify they fail**

```
pytest tests/unit/applier/test_read_wide_stage_column_sub_cols.py -v
```

Expected: FAIL — `_read_wide_stage_column` currently doesn't iterate `sub_columns`.

- [ ] **Step 9.3: Replace `_read_wide_stage_column` with stage-column-aware version**

In `app/services/applier/apply_plan.py`, replace `_read_wide_stage_column` (apply_plan.py:88-108) and its caller `_read_stages` (apply_plan.py:147-166).

First, refactor `_read_wide_stage_column` to accept a `StageColumn`:

```python
def _read_wide_stage_column(ws, band: StageBandSpec, stage_col: StageColumn,
                            pli_row: int, name_map: CanonicalNameMap) -> Stage | None:
    """Read one stage column in wide_sub_columns layout for `pli_row`.

    primary_col → planned_date. Each sub_column is canonicalised via
    name_map.stage_subfield_labels; canonical Stage fields write to the Stage
    record, everything else goes into Stage.metadata. Returns None when the
    primary cell is empty or the stage is mapped to "ignore".
    """
    canonical_stage = name_map.stage_names.get(stage_col.name, stage_col.name)
    if canonical_stage == "ignore":
        return None
    c_idx = column_index_from_string(stage_col.primary_col)
    pv, pa = _read_with_merge(ws, pli_row, c_idx)
    if pv is None:
        return None

    metadata: dict = {}
    source_cells: dict[str, str] = {"planned_date": pa}
    stage_fields: dict = {}

    for raw_sub, sub_col in stage_col.sub_columns.items():
        canonical_sub = name_map.stage_subfield_labels.get(raw_sub, raw_sub)
        if canonical_sub == "ignore":
            continue
        sv, sa = _read_with_merge(ws, pli_row, column_index_from_string(sub_col))
        if sv is None:
            continue
        if canonical_sub in Stage.model_fields and canonical_sub not in {"name", "source"}:
            stage_fields[canonical_sub] = sv
        else:
            metadata[canonical_sub] = sv
        source_cells[canonical_sub] = sa

    return Stage(
        name=canonical_stage,
        planned_date=pv if isinstance(pv, (date, datetime)) else None,
        section=band.name, metadata=metadata,
        source={"sheet": ws.title, "rows": [pli_row], "cells": source_cells},
        **stage_fields,
    )
```

Then update `_read_stages` to dispatch on `band.stage_columns` when present, falling back to `band.stage_cols`:

```python
def _read_stages(ws, bands: list[StageBandSpec], pli_row: int,
                 name_map: CanonicalNameMap, parent_source: dict) -> list[Stage]:
    """Collect all Stage objects for a PLI row across every stage band."""
    stages: list[Stage] = []
    for band in bands:
        stage_columns = band.stage_columns or [
            StageColumn(name=name, name_cell=f"{col}{band.sub_header_row}",
                         primary_col=col)
            for name, col in band.stage_cols.items()
        ]
        if band.layout_mode == "wide_sub_columns":
            for sc in stage_columns:
                stage = _read_wide_stage_column(ws, band, sc, pli_row, name_map)
                if stage is not None:
                    stages.append(stage)
        else:  # tall_sub_rows — unchanged behaviour
            for sc in stage_columns:
                stage = _read_tall_stage_column(
                    ws, band, sc.name, sc.primary_col, name_map)
                if stage is not None:
                    stages.append(stage)
    return stages
```

Add the import for `StageColumn`:

```python
from app.models.artifacts import (
    CanonicalNameMap,
    KVAnchor,
    PliBlock,
    RowSpec,
    SheetPlan,
    StageBandSpec,
    StageColumn,
)
```

- [ ] **Step 9.4: Run tests to verify they pass**

```
pytest tests/unit/applier/test_read_wide_stage_column_sub_cols.py -v
```

Expected: 2 PASS.

- [ ] **Step 9.5: Run the full test suite**

```
pytest tests -q -m "not live"
```

Expected: all PASS. The tall_sub_rows path is preserved (existing SHEET_IS_PLI fixtures still emit 18-20 stages).

- [ ] **Step 9.6: Commit**

```bash
git add app/services/applier/apply_plan.py tests/unit/applier/test_read_wide_stage_column_sub_cols.py
git commit -m "feat(applier): route stage sub_columns to Stage fields or metadata"
```

---

## Task 10: apply_plan — write confidence in section + sheet emit paths

**Files:**
- Modify: `app/services/applier/apply_plan.py`
- Test: extend `tests/unit/applier/test_emit_single_row_pli_header_labels.py` with section + sheet cases

**Context:** Tasks 8+9 wired confidence into `_emit_single_row_pli` and `_read_kv_into`. The section + sheet emit paths use `_read_kv_into` (so they already inherit confidence) — verify via test. No code change expected unless test reveals a gap.

- [ ] **Step 10.1: Add confidence-coverage tests**

Append to `tests/unit/applier/test_emit_single_row_pli_header_labels.py`:

```python
from app.enums.pli_mode import PliMode as _Mode
from app.models.artifacts import KVAnchor, PliBlock


def test_sheet_is_pli_writes_confidence(tmp_path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A1"] = "IO #"
    ws["B1"] = "1063"
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ctx = register_workbook(p)
    plan = SheetPlan(
        sheet="S", pli_mode=_Mode.SHEET_IS_PLI,
        kv_anchors=[KVAnchor(label_cell="A1", value_cell="B1", field="IO #")],
    )
    nm = CanonicalNameMap(field_labels={"IO #": "io_number"})
    plis = apply_plan(ctx, plan, nm)
    assert plis[0].confidence.get("io_number") == 0.95  # kv_anchor default


def test_section_per_pli_writes_confidence(tmp_path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A2"] = "IO #"
    ws["B2"] = "1063"
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ctx = register_workbook(p)
    block = PliBlock(
        id=0, bbox=(2, 5),
        identity=[KVAnchor(label_cell="A2", value_cell="B2", field="IO #")],
    )
    plan = SheetPlan(
        sheet="S", pli_mode=_Mode.SECTION_PER_PLI,
        pli_blocks=[block],
    )
    nm = CanonicalNameMap(field_labels={"IO #": "io_number"})
    plis = apply_plan(ctx, plan, nm)
    assert plis[0].confidence.get("io_number") == 0.95
```

- [ ] **Step 10.2: Run tests**

```
pytest tests/unit/applier/test_emit_single_row_pli_header_labels.py -v
```

Expected: PASS if `_read_kv_into` confidence write from Task 8 covered SECTION + SHEET. If not, repeat the `values.setdefault("confidence", {})[canonical] = ...` pattern in `_apply_section_per_pli` and `_apply_sheet_is_pli`.

- [ ] **Step 10.3: Commit**

```bash
git add tests/unit/applier/test_emit_single_row_pli_header_labels.py app/services/applier/apply_plan.py
git commit -m "test(applier): assert confidence written across all emit paths"
```

---

## Task 11: FieldNamer — mode-agnostic `_build_user_input`

**Files:**
- Modify: `app/services/agents/field_namer.py`
- Test: `tests/agent/test_field_namer_row_per_pli_input.py`

**Context:** Replace `_build_user_input` to read from the union of all three identity channels and from `stage_columns`. Build a deterministic markdown body with identity / stage / sub-field sections.

- [ ] **Step 11.1: Write the failing test**

Create `tests/agent/test_field_namer_row_per_pli_input.py`:

```python
"""FieldNamer prompt body covers header_labels + stage_columns + sub_columns."""
from app.enums.pli_mode import PliMode
from app.models.artifacts import (
    HeaderLabel, KVAnchor, PliBlock, SheetPlan, StageBandSpec, StageColumn,
)
from app.services.agents.field_namer import _build_user_input


def _stub_ctx(*, max_row: int = 4, max_col: int = 26) -> object:
    class _WS:
        def __init__(self) -> None:
            self.max_row = max_row
            self.max_column = max_col
            self.title = "S"
        def cell(self, row, column):
            class _C:
                value = None
            return _C()
    class _WB:
        def __getitem__(self, _k): return _WS()
    class _Ctx:
        wb = _WB()
    return _Ctx()


def test_row_per_pli_emits_identity_section() -> None:
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_labels=[
            HeaderLabel(raw="IO NO", col="B", row=3),
            HeaderLabel(raw="STYLE", col="F", row=3),
        ],
    )
    body = _build_user_input(_stub_ctx(), {"plan": plan})
    assert "Identity labels detected" in body
    assert "'IO NO'" in body and "(col B)" in body
    assert "'STYLE'" in body and "(col F)" in body


def test_sheet_is_pli_emits_kv_anchor_labels() -> None:
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.SHEET_IS_PLI,
        kv_anchors=[KVAnchor(label_cell="A1", value_cell="B1", field="IO #")],
    )
    body = _build_user_input(_stub_ctx(), {"plan": plan})
    assert "'IO #'" in body


def test_section_per_pli_emits_block_identity() -> None:
    block = PliBlock(
        id=0, bbox=(2, 5),
        identity=[KVAnchor(label_cell="A2", value_cell="B2", field="IO #")],
    )
    plan = SheetPlan(sheet="S", pli_mode=PliMode.SECTION_PER_PLI, pli_blocks=[block])
    body = _build_user_input(_stub_ctx(), {"plan": plan})
    assert "'IO #'" in body


def test_emits_stage_sub_field_section_when_sub_columns_present() -> None:
    band = StageBandSpec(
        name="b", name_cell="U3", sub_header_row=3,
        stage_columns=[StageColumn(name="CUTTING", name_cell="U3", primary_col="U",
                                    sub_columns={"Actual": "V"})],
    )
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_labels=[HeaderLabel(raw="X", col="A", row=3)],
        stage_bands=[band],
    )
    body = _build_user_input(_stub_ctx(), {"plan": plan})
    assert "Stage sub-field labels" in body
    assert "'Actual'" in body
    assert "'CUTTING'" in body
```

- [ ] **Step 11.2: Run tests to verify they fail**

```
pytest tests/agent/test_field_namer_row_per_pli_input.py -v
```

Expected: FAILs — current `_build_user_input` does not surface `header_labels`, sub-fields, or use the new section headings.

- [ ] **Step 11.3: Rewrite `_build_user_input`**

Replace `_build_user_input` in `app/services/agents/field_namer.py`:

```python
def _build_user_input(ctx: object, inputs: dict) -> str:
    """Assemble the LLM prompt body from all identity + stage channels.

    Sources read symmetrically across the three pli_modes:
      ROW_PER_PLI     → plan.header_labels
      SHEET_IS_PLI    → plan.kv_anchors
      SECTION_PER_PLI → plan.pli_blocks[].identity
    Stage names + sub-field labels come from stage_columns on both sheet-level
    and block-level stage bands.
    """
    plan: SheetPlan = inputs["plan"]
    ws = ctx.wb[plan.sheet] if hasattr(ctx, "wb") else None

    identity: list[tuple[str, str]] = [(hl.raw, hl.col) for hl in plan.header_labels]
    identity.extend((kv.field, _col_of(kv.label_cell)) for kv in plan.kv_anchors)
    for blk in plan.pli_blocks:
        identity.extend((kv.field, _col_of(kv.label_cell)) for kv in blk.identity)

    stage_names: list[str] = []
    sub_field_labels: set[str] = set()
    all_bands = list(plan.stage_bands)
    for blk in plan.pli_blocks:
        all_bands.extend(blk.stage_bands)
    for band in all_bands:
        for sc in band.stage_columns or _legacy_columns(band):
            stage_names.append(sc.name)
            sub_field_labels.update(sc.sub_columns.keys())

    samples = _sample_values(ws, plan, identity, k=3) if ws is not None else {}
    return _format_markdown(plan.sheet, identity, stage_names, sub_field_labels, samples)


def _col_of(addr: str) -> str:
    """Return the column letter from a cell address like 'AA12'."""
    col_letter, _ = coordinate_from_string(addr)
    return col_letter


def _legacy_columns(band) -> list[StageColumn]:
    """Build StageColumn list from a band's legacy `stage_cols` dict."""
    return [
        StageColumn(name=name, name_cell=f"{col}{band.sub_header_row}",
                     primary_col=col)
        for name, col in band.stage_cols.items()
    ]


def _format_markdown(sheet: str, identity: list[tuple[str, str]],
                     stage_names: list[str], sub_field_labels: set[str],
                     samples: dict[str, list[object]]) -> str:
    """Render a deterministic markdown prompt body."""
    lines = [f"# Sheet: {sheet}", "", "## Identity labels detected:"]
    for raw, col in sorted(set(identity)):
        sample_blurb = ""
        if samples.get(raw):
            sample_blurb = "  samples: " + ", ".join(
                repr(s) for s in samples[raw][:3]
            )
        lines.append(f"  - {raw!r} (col {col}){sample_blurb}")
    lines.append("")
    lines.append("## Stage headers detected:")
    for name in sorted(set(stage_names)):
        lines.append(f"  - {name!r}")
    if sub_field_labels:
        lines.append("")
        lines.append("## Stage sub-field labels detected:")
        for sub in sorted(sub_field_labels):
            lines.append(f"  - {sub!r}")
    return "\n".join(lines)
```

Add at the top of the imports:

```python
from openpyxl.utils.cell import coordinate_from_string

from app.models.artifacts import (
    CanonicalNameMap, KVAnchor, SheetPlan, StageBandSpec, StageColumn,
)
```

The `_sample_values` helper is filled in Task 12 — leave a `def _sample_values(ws, plan, identity, k): return {}` stub for now so this task's tests pass.

```python
def _sample_values(ws, plan: SheetPlan, identity: list[tuple[str, str]],
                   k: int = 3) -> dict[str, list[object]]:
    """Placeholder; filled in Task 12."""
    return {}
```

- [ ] **Step 11.4: Run tests to verify they pass**

```
pytest tests/agent/test_field_namer_row_per_pli_input.py -v
```

Expected: 4 PASS.

- [ ] **Step 11.5: Run the full test suite**

```
pytest tests -q -m "not live"
```

Expected: existing FieldNamer agent tests still PASS — they use FakeLLM and don't assert on prompt body shape (verified by reading current tests/agent/ before changes). If a test breaks because it expected the old `## Detected labels:` heading, update the canned response or the assertion to match the new heading.

- [ ] **Step 11.6: Commit**

```bash
git add app/services/agents/field_namer.py tests/agent/test_field_namer_row_per_pli_input.py
git commit -m "feat(agent): FieldNamer reads identity from all three pli_mode channels"
```

---

## Task 12: FieldNamer — `_sample_values` helper

**Files:**
- Modify: `app/services/agents/field_namer.py`
- Test: `tests/agent/test_field_namer_value_sampling.py`

**Context:** For each identity label, pull up to `k` non-null sample values from the workbook to include in the prompt. Bound string length so the prompt stays small.

- [ ] **Step 12.1: Write the failing test**

Create `tests/agent/test_field_namer_value_sampling.py`:

```python
"""_sample_values returns ≤k non-null samples per identity column."""
import openpyxl
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.models.artifacts import HeaderLabel, RowSpec, SheetPlan
from app.repositories.workbook_repo import register_workbook
from app.services.agents.field_namer import _sample_values


def test_returns_at_most_k_samples_per_label(tmp_path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["B3"] = "IO NO"
    ws["B4"] = 1063
    ws["B5"] = 1064
    ws["B6"] = 1065
    ws["B7"] = 1066
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ctx = register_workbook(p)
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        rows=[RowSpec(idx=r, role=RowRole.ANCHOR) for r in (4, 5, 6, 7)],
        header_labels=[HeaderLabel(raw="IO NO", col="B", row=3)],
    )
    samples = _sample_values(ctx.wb["S"], plan, [("IO NO", "B")], k=3)
    assert samples["IO NO"] == [1063, 1064, 1065]


def test_skips_null_cells(tmp_path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["B3"] = "IO NO"
    ws["B4"] = None
    ws["B5"] = 1064
    ws["B6"] = None
    ws["B7"] = 1066
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ctx = register_workbook(p)
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        rows=[RowSpec(idx=r, role=RowRole.ANCHOR) for r in (4, 5, 6, 7)],
        header_labels=[HeaderLabel(raw="IO NO", col="B", row=3)],
    )
    samples = _sample_values(ctx.wb["S"], plan, [("IO NO", "B")], k=3)
    assert samples["IO NO"] == [1064, 1066]


def test_returns_empty_for_label_with_no_data_rows(tmp_path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["B3"] = "X"
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ctx = register_workbook(p)
    plan = SheetPlan(sheet="S", pli_mode=PliMode.ROW_PER_PLI, header_labels=[])
    samples = _sample_values(ctx.wb["S"], plan, [("X", "B")], k=3)
    assert samples.get("X") in (None, [])
```

- [ ] **Step 12.2: Run tests to verify they fail**

```
pytest tests/agent/test_field_namer_value_sampling.py -v
```

Expected: FAILs — `_sample_values` returns `{}` (placeholder from Task 11).

- [ ] **Step 12.3: Implement `_sample_values`**

Replace the stub in `app/services/agents/field_namer.py`:

```python
def _sample_values(ws, plan: SheetPlan, identity: list[tuple[str, str]],
                   k: int = 3) -> dict[str, list[object]]:
    """Return up to `k` non-null sample values per identity label.

    For ROW_PER_PLI: reads data rows from `plan.rows` (ANCHOR/CHILD).
    For SHEET_IS_PLI / SECTION_PER_PLI: returns {} — KV labels carry their own
    values, no sampling needed.
    String values are truncated to 60 chars to keep prompt size bounded.
    """
    from openpyxl.utils import column_index_from_string
    if plan.pli_mode is not PliMode.ROW_PER_PLI:
        return {}
    data_rows = [r.idx for r in plan.rows
                 if r.role.value in {"anchor", "child"}]
    if not data_rows:
        return {}
    out: dict[str, list[object]] = {}
    for raw, col in identity:
        col_idx = column_index_from_string(col)
        seen: list[object] = []
        for r in data_rows:
            if len(seen) >= k:
                break
            v = ws.cell(row=r, column=col_idx).value
            if v is None:
                continue
            if isinstance(v, str) and len(v) > 60:
                v = v[:57] + "..."
            seen.append(v)
        if seen:
            out[raw] = seen
    return out
```

Add the `PliMode` import to field_namer.py (in local-imports group):

```python
from app.enums.pli_mode import PliMode
```

- [ ] **Step 12.4: Run tests to verify they pass**

```
pytest tests/agent/test_field_namer_value_sampling.py -v
```

Expected: 3 PASS.

- [ ] **Step 12.5: Commit**

```bash
git add app/services/agents/field_namer.py tests/agent/test_field_namer_value_sampling.py
git commit -m "feat(agent): _sample_values for FieldNamer prompt context"
```

---

## Task 13: FieldNamer prompt updates

**Files:**
- Modify: `app/prompts/workflow/field_namer.md`

**Context:** Expand canonical vocab; add stage sub-field canonical names; mention optional confidence outputs. Pure markdown change; FakeLLM-based agent tests verify behavior without parsing the prompt.

- [ ] **Step 13.1: Replace the prompt**

Replace the contents of `app/prompts/workflow/field_namer.md`:

```markdown
You are FieldNamer. Map supplier labels, stage column headers, and stage sub-field
labels to canonical names.

Canonical PLI field names:
  io_number, style_code, style_name, color_code, color_name, fabric_code,
  delivery_date, quantity, order_quantity, plan_quantity, order_receipt_date,
  pps_completion, sample_completion, ex_factory_date, buyer, season, factory,
  article_no, price, balance_qty, buyer_po_no, fabric_quality, cut_qty,
  sewing_qty, shipped_qty, etd_ex_factory, sample_dispatch

Canonical stage names (drop into Stage.name):
  fabric, lab_dip_send, lab_dip_approval, fit_send, fit_approval,
  art_work_send, art_work_approval, in_house_fabric_send,
  in_house_fabric_approval, pre_production_send, pre_production_approval,
  first_pattern, garment_pattern, planned_completion_date,
  size_set, lot_card, cutting, feeding, sewing, final_inspection,
  printing, embroidery, washing, finishing, packing

Canonical stage sub-field names (for wide_sub_columns with sub-cols):
  planned_date, actual_date, approval_date, received_date,
  approved_qty, quantity, remarks, comments, deviation_days

Output JSON matching CanonicalNameMap:
- field_labels: {original_label: canonical_field_name | "ignore"}
- stage_names: {original_stage_header: canonical_stage_name | "ignore"}
- stage_subfield_labels: {original_sub_label: canonical_subfield | "ignore"}
- field_confidence: optional {canonical_field: 0.0–1.0}
- stage_confidence: optional {canonical_stage: 0.0–1.0}

Use "ignore" for labels that aren't worth extracting.

When you see sample values in parentheses after a label, use them to infer the
canonical name when the label itself is ambiguous (e.g. a 4-digit integer column
with values like 1063 is likely io_number even if the label is "Job #").

{{SHARED}}
```

- [ ] **Step 13.2: Run the test suite**

```
pytest tests -q -m "not live"
```

Expected: existing FieldNamer agent tests still PASS (FakeLLM stubs canned responses, not real LLM).

- [ ] **Step 13.3: Commit**

```bash
git add app/prompts/workflow/field_namer.md
git commit -m "docs(prompt): expand FieldNamer canonical vocab + sub-field section"
```

---

## Task 14: Add fixture — `row_per_pli_wide_single_row_strip` (CB-shape)

**Files:**
- Create: `tests/fixtures/builders/row_per_pli_wide_single_row_strip.py`
- Create: `tests/fixtures/expected/row_per_pli_wide_single_row_strip.json`

**Context:** Minimal CB-shape: 1 sheet with a single-row stage strip + 2 data rows.

- [ ] **Step 14.1: Create the builder**

Create `tests/fixtures/builders/row_per_pli_wide_single_row_strip.py`:

```python
"""Christian Berg-shape minimal fixture: single-row stage strip, ROW_PER_PLI."""
from datetime import date
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    """Populate a wb with a CB-style single-row stage strip layout."""
    ws = wb.active
    ws.title = "CB"
    # Header row 3
    ws["A3"] = "S NO"
    ws["B3"] = "IO NO"
    ws["F3"] = "STYLE"
    ws["K3"] = "COLOR"
    ws["L3"] = "ORDER QTY"
    ws["D3"] = "EX FAC DATE"
    ws["N3"] = "FABRIC"
    ws["U3"] = "CUTTING"
    ws["V3"] = "Actual"
    ws["AE3"] = "SEWING"
    # Row 4
    ws["A4"] = 1
    ws["B4"] = 1063
    ws["F4"] = "T-STYLE"
    ws["K4"] = "422-MAG"
    ws["L4"] = 2356
    ws["D4"] = date(2026, 5, 5)
    ws["N4"] = date(2026, 3, 18)
    ws["U4"] = date(2026, 3, 12)
    ws["V4"] = date(2026, 3, 16)
    ws["AE4"] = date(2026, 4, 3)
    # Row 5
    ws["A5"] = 2
    ws["B5"] = 1064
    ws["F5"] = "T-STYLE2"
    ws["K5"] = "630-NAV"
    ws["L5"] = 2050
    ws["D5"] = date(2026, 5, 5)
    ws["N5"] = date(2026, 3, 25)
    ws["U5"] = date(2026, 4, 16)
    ws["V5"] = date(2026, 4, 20)
    ws["AE5"] = date(2026, 4, 25)
```

- [ ] **Step 14.2: Create the expected JSON**

Create `tests/fixtures/expected/row_per_pli_wide_single_row_strip.json`:

```json
{
  "fixture": "row_per_pli_wide_single_row_strip",
  "description": "CB-shape: single-row stage strip with ORDER QTY/COLOR/EX FAC + Fabric/Cutting/Sewing stages.",
  "layer_expectations": {
    "flow": {
      "pli_mode": "row_per_pli",
      "header_labels_count_min": 5,
      "stage_bands_count": 1,
      "stage_columns_min": 3,
      "negatives": {
        "kv_anchors_empty": true,
        "pli_blocks_empty": true
      }
    },
    "e2e": {
      "pli_count": 2,
      "first_pli": {
        "io_number_truthy": true,
        "delivery_date_truthy": true,
        "quantity_truthy": true,
        "stages_min": 2
      },
      "extraction_confidence_min": 0.5
    },
    "agent": {
      "field_namer_canned": {
        "field_labels": {
          "S NO": "ignore",
          "IO NO": "io_number",
          "STYLE": "style_code",
          "COLOR": "color_code",
          "ORDER QTY": "quantity",
          "EX FAC DATE": "delivery_date"
        },
        "stage_names": {
          "FABRIC": "fabric",
          "CUTTING": "cutting",
          "SEWING": "sewing"
        },
        "stage_subfield_labels": {
          "Actual": "actual_date"
        }
      }
    }
  },
  "failure_expectations": null
}
```

- [ ] **Step 14.3: Run any existing fixture-walker test against the new fixture**

```
pytest tests -q -m "not live" -k "wide_single_row_strip"
```

Expected: any test using `@fixture_case("row_per_pli_wide_single_row_strip")` runs and asserts the expectations. If no test references it yet, the fixture is in place for Task 17.

- [ ] **Step 14.4: Commit**

```bash
git add tests/fixtures/builders/row_per_pli_wide_single_row_strip.py tests/fixtures/expected/row_per_pli_wide_single_row_strip.json
git commit -m "test(fixture): add row_per_pli_wide_single_row_strip (CB-shape)"
```

---

## Task 15: Add fixture — `row_per_pli_wide_two_row_strip` (DKN-shape)

**Files:**
- Create: `tests/fixtures/builders/row_per_pli_wide_two_row_strip.py`
- Create: `tests/fixtures/expected/row_per_pli_wide_two_row_strip.json`

**Context:** DKN-shape: two-row header where row N has stage names (merged horizontally across the stage's columns) and row N+1 has Plan/Actual sub-labels per column.

- [ ] **Step 15.1: Create the builder**

Create `tests/fixtures/builders/row_per_pli_wide_two_row_strip.py`:

```python
"""DKN-shape minimal fixture: two-row stage header (name row + sub-label row)."""
from datetime import date
from openpyxl import Workbook
from openpyxl.utils import get_column_letter


def build(wb: Workbook) -> None:
    """Populate a wb with a DKN-style two-row stage header layout."""
    ws = wb.active
    ws.title = "DKN"
    # Row 1 identity headers (merged across only one col each)
    ws["B1"] = "Buyer Po No"
    ws["C1"] = "Color"
    ws["D1"] = "Order Qty"
    ws["E1"] = "Etd Ex factory as per P.O"
    # Row 1 stage names merged across each stage's column block
    # CUTTING spans cols H..I (Plan, Actual); SEWING spans J..K
    ws["H1"] = "CUTTING"
    ws.merge_cells("H1:I1")
    ws["J1"] = "SEWING"
    ws.merge_cells("J1:K1")
    # Row 2 sub-labels under each stage
    ws["H2"] = "Plan"
    ws["I2"] = "Actual"
    ws["J2"] = "Plan"
    ws["K2"] = "Actual"
    # Data row 3
    ws["B3"] = "PO-00045"
    ws["C3"] = "Navy"
    ws["D3"] = 500
    ws["E3"] = date(2026, 5, 5)
    ws["H3"] = date(2026, 3, 12)
    ws["I3"] = date(2026, 3, 16)
    ws["J3"] = date(2026, 4, 3)
    ws["K3"] = date(2026, 4, 5)
```

- [ ] **Step 15.2: Create the expected JSON**

Create `tests/fixtures/expected/row_per_pli_wide_two_row_strip.json`:

```json
{
  "fixture": "row_per_pli_wide_two_row_strip",
  "description": "DKN-shape: two-row stage header — stage names row + Plan/Actual sub-label row.",
  "layer_expectations": {
    "flow": {
      "pli_mode": "row_per_pli",
      "header_labels_count_min": 3,
      "stage_bands_count": 1,
      "stage_columns_min": 2,
      "first_stage_column": {
        "name": "CUTTING",
        "primary_col": "H",
        "sub_columns_keys": ["Actual"]
      }
    },
    "e2e": {
      "pli_count": 1,
      "first_pli": {
        "delivery_date_truthy": true,
        "quantity_truthy": true,
        "stages_min": 2
      }
    },
    "agent": {
      "field_namer_canned": {
        "field_labels": {
          "Buyer Po No": "buyer_po_no",
          "Color": "color_code",
          "Order Qty": "quantity",
          "Etd Ex factory as per P.O": "delivery_date"
        },
        "stage_names": {
          "CUTTING": "cutting",
          "SEWING": "sewing"
        },
        "stage_subfield_labels": {
          "Actual": "actual_date"
        }
      }
    }
  },
  "failure_expectations": null
}
```

- [ ] **Step 15.3: Commit**

```bash
git add tests/fixtures/builders/row_per_pli_wide_two_row_strip.py tests/fixtures/expected/row_per_pli_wide_two_row_strip.json
git commit -m "test(fixture): add row_per_pli_wide_two_row_strip (DKN-shape)"
```

---

## Task 16: Update existing ROW_PER_PLI fixture expected.json files

**Files:**
- Modify: any `tests/fixtures/expected/*.json` whose `layer_expectations.flow.pli_mode == "row_per_pli"`

**Context:** Now that the planner emits `header_labels` for ROW_PER_PLI, existing fixtures pin `pli_mode=row_per_pli` should also assert `header_labels_count_min ≥ 1` to lock the new behavior. Discover them via grep, then add the assertion.

- [ ] **Step 16.1: List ROW_PER_PLI fixtures**

```
grep -l '"pli_mode": "row_per_pli"' tests/fixtures/expected/*.json
```

Capture the list. For each one not already updated by this plan (Tasks 14/15 are already new).

- [ ] **Step 16.2: For each ROW_PER_PLI fixture, add the assertion**

In each fixture's `layer_expectations.flow` block, add:

```json
"header_labels_count_min": 1,
```

Example: `tests/fixtures/expected/tabular_simple.json` before:

```json
"flow": {
  "pli_mode": "row_per_pli",
  "rows_count_min": 1,
  "negatives": {"kv_anchors_empty": true, "pli_blocks_empty": true}
}
```

After:

```json
"flow": {
  "pli_mode": "row_per_pli",
  "rows_count_min": 1,
  "header_labels_count_min": 1,
  "negatives": {"kv_anchors_empty": true, "pli_blocks_empty": true}
}
```

If the fixture-loader doesn't yet recognise `header_labels_count_min`, see Task 17.

- [ ] **Step 16.3: Run the full test suite**

```
pytest tests -q -m "not live"
```

Expected: all PASS.

- [ ] **Step 16.4: Commit**

```bash
git add tests/fixtures/expected/*.json
git commit -m "test(fixture): assert header_labels_count_min on existing ROW_PER_PLI fixtures"
```

---

## Task 17: Wire `header_labels_count_min` + new SECTION/failure fixture loaders

**Files:**
- Modify: the fixture-loader module (find via `grep -r "layer_expectations" tests/`)

**Context:** Add support in the fixture-runner for the new assertion keys: `header_labels_count_min`, `stage_columns_min`, `first_stage_column`, `negatives.kv_anchors_empty`, `field_namer_canned`. Then wire failure fixtures from the spec (section_per_pli_blocks_with_identity, failure_segmenter_block_empty, failure_multiple_identity_channels) into the matching parametrize blocks.

- [ ] **Step 17.1: Locate the fixture-loader**

```
grep -rn "layer_expectations" tests/conftest.py tests/fixtures/ 2>/dev/null | head -20
```

The expectations parser likely lives at `tests/conftest.py` or `tests/fixtures/_loader.py`. Read it and identify where assertion keys are consumed.

- [ ] **Step 17.2: Add new assertion keys**

For each missing key, add a branch in the loader/runner. Example pseudo-shape:

```python
if "header_labels_count_min" in flow:
    assert len(plan.header_labels) >= flow["header_labels_count_min"]
if "stage_columns_min" in flow:
    total = sum(len(b.stage_columns) for b in plan.stage_bands)
    assert total >= flow["stage_columns_min"]
if "first_stage_column" in flow:
    spec = flow["first_stage_column"]
    sc = plan.stage_bands[0].stage_columns[0]
    if "name" in spec: assert sc.name == spec["name"]
    if "primary_col" in spec: assert sc.primary_col == spec["primary_col"]
    if "sub_columns_keys" in spec:
        assert set(sc.sub_columns.keys()) >= set(spec["sub_columns_keys"])
```

- [ ] **Step 17.3: Run the fixture tests**

```
pytest tests/flow -q
```

Expected: all PASS, including the two new fixtures from Tasks 14 and 15.

- [ ] **Step 17.4: Commit**

```bash
git add tests/conftest.py tests/fixtures/_loader.py
git commit -m "test(fixtures): support new assertion keys for symmetric contract"
```

---

## Task 18: Add live regression test for 4 broken-family files

**Files:**
- Create: `tests/live/test_extract_live_regression.py`

**Context:** Lock the Phase 1 outcome: every previously-empty-husk file now returns canonical fields, stages, and non-zero confidence.

- [ ] **Step 18.1: Create the live regression test**

Create `tests/live/test_extract_live_regression.py`:

```python
"""Live regression: each previously-broken file must extract canonical fields + stages."""
from pathlib import Path

import pytest

from app.services.extraction import extract


@pytest.mark.live
@pytest.mark.parametrize("xlsx", [
    "CHRISTIAN BERG- T&A.xlsx",
    "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
    "FA26 YC & EUROPE T&A #1.xlsx",
    "NORTHERN REFLECTIONS- T&a.xlsx",
])
def test_live_extraction_produces_canonical_fields(xlsx) -> None:
    """Every PLI must have ≥1 canonical field; ≥1 PLI must have stages; conf > 0.4."""
    result = extract(Path("dataset") / xlsx)
    assert len(result.plis) >= 1, f"{xlsx}: no PLIs returned"
    assert any(p.io_number for p in result.plis), f"{xlsx}: no io_number anywhere"
    assert any(p.style_code for p in result.plis), f"{xlsx}: no style_code anywhere"
    assert any(p.stages for p in result.plis), f"{xlsx}: no stages on any PLI"
    assert result.extraction_confidence > 0.4, \
        f"{xlsx}: extraction_confidence={result.extraction_confidence}"
```

- [ ] **Step 18.2: Run the live test**

```
pytest tests/live/test_extract_live_regression.py -m live -v
```

Requires `ANTHROPIC_API_KEY` in `.env`. Expected: 4 PASS. If any fail, the failure points at residual bugs not covered by Phase 1 (e.g., MOP's planner-misclassification cousin — see "Open / deferred" in spec).

- [ ] **Step 18.3: Commit**

```bash
git add tests/live/test_extract_live_regression.py
git commit -m "test(live): regression for CB/DKN/FA26/NR canonical extraction"
```

---

## Task 19: Update CLAUDE.md + ARCHITECTURE.md + new ADR

**Files:**
- Modify: `CLAUDE.md`, `ARCHITECTURE.md`
- Create: `docs/adrs/0006-symmetric-artifact-contract.md`
- Modify: `docs/adrs/README.md`

**Context:** Per `docs/PRINCIPLES.md` §8, docs update AFTER implementation. Phase 1 is now implementation-complete; docs catch up.

- [ ] **Step 19.1: Write ADR 0006**

Create `docs/adrs/0006-symmetric-artifact-contract.md`:

```markdown
# 0006 — Symmetric planner→agent contract

**Date:** 2026-05-19 (design); <implementation-date> (implemented)
**Status:** Accepted

## Context

After SheetRowPlanner shipped (ADR-0003), an empirical probe across 9
representative files showed eight had broken extraction: ROW_PER_PLI files
returned empty canonical fields; SECTION_PER_PLI returned empty PLI husks;
only SHEET_IS_PLI partially worked (3-4/8 canonical fields, no confidence).
Root cause: the `SheetPlan` artifact was designed around SHEET_IS_PLI and
under-specified the identity channel for ROW_PER_PLI (column headers lived
only as cell values in `header_rows`, never lifted into the artifact) and
the stage_columns structure for wide_sub_columns layouts (one column per
stage, no sub-column representation).

## Decision

Extend `SheetPlan` symmetrically across the three pli_modes. New fields,
all defaulted (additive):

- `HeaderLabel` type; `SheetPlan.header_labels` populated for ROW_PER_PLI.
- `StageColumn` (resurrected from artifacts.py:127); `StageBandSpec.stage_columns`
  carries primary_col + sub_columns per stage.
- `KVAnchor.confidence` default 0.95.
- `CanonicalNameMap.stage_subfield_labels`, `field_confidence`,
  `stage_confidence` (optional LLM outputs).

`apply_plan` writes per-field `PLI.confidence`. New Tier 1 invariants enforce
mode↔channel exclusivity. `FieldNamer._build_user_input` reads symmetrically
across all three identity channels and includes sample values.

`apply_plan` determinism (ADR-0003 D3) preserved; agent set unchanged
(ADR-0001); faithful extraction (ADR-0002) untouched.

## Consequences

**Easier:**
- All three pli_modes feed FieldNamer + apply_plan symmetrically.
- New supplier vocab is supplemented by value-sample inference in the prompt.
- `extraction_confidence` reflects quality (was always 0.0).

**Harder / constrained:**
- `stage_cols` remains as a deprecated alias for one release. To delete after
  Phase 1 stabilises.

**What we gave up:**
- The `stage_cols` flat representation; transitional period only.

## Alternatives considered

- **LabelScout agent** (LLM-pull with new tools) — rejected as Phase 1: would
  double LLM cost per sheet for a fix that's mostly a missing artifact slot.
  Retained as Phase 4 escape hatch if novel-layout vocab continues to drift.
- **Per-family classifier** — rejected; violates ADR-0001 routing principle.
```

- [ ] **Step 19.2: Add ADR to the README table**

Edit `docs/adrs/README.md` to add:

```markdown
| 0006 | 2026-05-19 | Symmetric planner→agent contract | Accepted |
```

- [ ] **Step 19.3: Update CLAUDE.md "Current state" section**

In `CLAUDE.md`, update the "Current state" paragraph to mention the symmetric contract delivery and the new test count (~225 → exact count after Phase 1 lands).

- [ ] **Step 19.4: Update ARCHITECTURE.md**

In `ARCHITECTURE.md` §"Bridge artifacts (data flow)", update the artifact-schema table to include `header_labels`, `stage_columns`, `confidence` on KVAnchor, and the new fields on CanonicalNameMap. Update the "Channel ↔ mode matrix" in the SheetRowPlanner section.

- [ ] **Step 19.5: Commit**

```bash
git add docs/adrs/0006-symmetric-artifact-contract.md docs/adrs/README.md CLAUDE.md ARCHITECTURE.md
git commit -m "docs: ADR-0006 + ARCHITECTURE/CLAUDE updates for symmetric contract"
```

---

## Task 20: Phase 1 exit verification + final probe

**Files:** none (verification only)

- [ ] **Step 20.1: Run the full non-live test suite**

```
pytest tests -q -m "not live"
```

Expected: all PASS. Test count ~225 (≈209 baseline + 16 new).

- [ ] **Step 20.2: Run the live test suite**

```
pytest tests -m live -q
```

Expected: PASS (including new regression tests).

- [ ] **Step 20.3: Run `make eval` if labelled fixtures exist**

```
make eval
```

Expected: scoreboard monotonically improves on every previously-labelled file. Specifically: `field_recall` and `stage_recall` for `CHRISTIAN BERG` increase from 0 → ≥ 0.7.

- [ ] **Step 20.4: Probe `/extract` against the dataset (sanity)**

```
make up
sleep 5
for f in "CHRISTIAN BERG- T&A.xlsx" "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx" "FA26 YC & EUROPE T&A #1.xlsx" "63261-TNA.xlsx"; do
  echo ">>> $f"
  curl -s -F "file=@dataset/${f}" http://localhost:8000/extract | \
    python3 -c "import sys,json; r=json.load(sys.stdin); print('  PLIs:', len(r['plis']), ' conf:', r['extraction_confidence'], ' io_set:', sum(1 for p in r['plis'] if p.get('io_number')))"
done
make down
```

Expected: every file shows `PLIs > 0`, `conf > 0.4`, `io_set > 0`.

- [ ] **Step 20.5: Commit a journey-doc update**

Append a "Phase 9 — Symmetric contract" section to `docs/JOURNEY.md` summarising the work (≤ 200 words). Commit.

```bash
git add docs/JOURNEY.md
git commit -m "docs(journey): record Phase 9 symmetric planner-agent contract"
```

- [ ] **Step 20.6: Phase 1 done — open follow-up tickets/issues for**

Per spec "Open / deferred":
- MOP Compass Pro "1 PLI" misclassification.
- Stage band detector per-band confidence reflecting vocab-match strength.
- Phase 2: vocab expansion against the broader probe data.
- Phase 3: label `63261-TNA`, `new job-TNA`, `FA26 YC & EUROPE T&A #1`,
  `20260129 DKN ...`, `NORTHERN REFLECTIONS- T&a`.

---

## Self-review summary

**Spec coverage check:**
- §"Bridge artifact changes" → Task 1 covers all five deltas.
- §"Sub-detector changes" 3.1 → Task 5 (`_collect_header_labels`).
- §"Sub-detector changes" 3.2 → Task 4 (reframed as warning emission — see plan note).
- §"Sub-detector changes" 3.3 → Tasks 2 + 3 (wide_sub_columns single + two-row).
- §"FieldNamer + apply_plan changes" 4.1 → Task 11.
- §"FieldNamer + apply_plan changes" 4.2 → Task 13.
- §"FieldNamer + apply_plan changes" 4.3A → Task 8.
- §"FieldNamer + apply_plan changes" 4.3B → Task 9.
- §"FieldNamer + apply_plan changes" 4.3C → Task 7 + Task 10.
- §"Error handling" — graceful-degradation paths covered by Task 4 (block empty) + Task 6 (invariants) + retained existing fallback in `_emit_single_row_pli`.
- §"Testing strategy" — Tasks 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 cover the listed unit tests; Tasks 14, 15 cover the new fixtures; Tasks 16, 17 cover existing-fixture updates and loader support; Task 18 covers the live regression.
- §"Rollout phasing" Phase 1 — covered by Tasks 1-20.
- §"Coding standard adherence" — referenced in plan header; each task uses verb-first names, modern types, ≤40-line functions, etc.

**Placeholder scan:** none.

**Type consistency:**
- `StageColumn`: same signature (name, name_cell, primary_col, sub_columns) used in Tasks 1, 2, 3, 5, 9, 11.
- `HeaderLabel`: same shape (raw, col, row, confidence) used in Tasks 1, 5, 8, 11.
- `_resolve_confidence` signature (kwargs: source, name_map, raw, canonical) consistent in Tasks 7, 8, 9.
- `_build_user_input(ctx, inputs)` signature unchanged from existing.

**Risks captured:**
- Task 17 (fixture-loader update) is empirically the most likely to need iteration — the exact shape of expected-key parsing depends on what's already in `tests/conftest.py`. The task is structured so any missing key gets added at first sight.
- Task 19 docs work depends on Phase 1 implementation behaviour matching expectations; if `extraction_confidence` lands at < 0.4 on any file, the ADR's "extraction_confidence reflects quality" claim is overstated and needs softening before commit.
