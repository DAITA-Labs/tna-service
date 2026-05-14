# SheetRowPlanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the LLM-led iteration system (`BoundaryFinder` + `IdentityLocator` + `QuantityDateLocator` + `StageLocator` + 4 pattern handlers + `field_applier` + `stage_applier`) with a deterministic `SheetRowPlanner` that emits a unified `SheetPlan` artifact and a fully deterministic `apply_plan` that consumes it. LLM is used only as a reviewer/judge (`PlanReviewer`), an ambiguity disambiguator (`LayoutHinter`), and a vocabulary mapper (`FieldNamer`).

**Architecture:** Deterministic Python (a `planner/` subsystem of 6 modules) classifies every row of every sheet into a `SheetPlan` covering three orthogonal axes (PLI scope × Stage scope × PLI height). Three new LLM agents (`LayoutHinter`, `PlanReviewer`, `FieldNamer`) fire only when needed. Two new plan validators check structural and statistical invariants of the plan; the four existing extraction validators stay unchanged. `apply_plan` is a pure function from `(SheetPlan, CanonicalNameMap)` to `list[PLI]` with zero LLM calls.

**Tech Stack:** Python 3.11+, Pydantic v2, openpyxl, Haystack components, Anthropic SDK, pytest. Existing tool registry + `WorkbookCtx` cache unchanged. Spec: `docs/superpowers/specs/2026-05-13-sheet-row-planner-design.md`.

**Conventions:**
- Tests use `.venv/Scripts/python.exe -m pytest tests -q` (project venv lives at the repo root).
- Code comments do NOT mention task numbers or plan references.
- Commits happen at the end of every task. Repo is the `tna-service` directory.

---

## File structure

**New files (planner subsystem):**
- `app/enums/pli_mode.py` — `PliMode` enum
- `app/enums/row_role.py` — `RowRole`, `SubRowRole` enums
- `app/enums/stage_scope.py` — `StageScope` enum
- `app/models/artifacts.py` — extend with `SheetSignals`, `RowSpec`, `KVAnchor`, `StageBandSpec`, `PliBlock`, `SheetPlan`, `CanonicalNameMap`, `LayoutHints`, `PlanVerdict`
- `app/services/planner/__init__.py`
- `app/services/planner/surveyor.py` — `SheetSurveyor` → `SheetSignals`
- `app/services/planner/row_classifier.py` — `classify_rows()` → `list[RowSpec]`
- `app/services/planner/block_segmenter.py` — `segment_blocks()` → `list[PliBlock]`
- `app/services/planner/kv_anchor_detector.py` — `detect_kv_anchors()` → `list[KVAnchor]`
- `app/services/planner/stage_band_detector.py` — `detect_stage_bands()` → `list[StageBandSpec]`
- `app/services/planner/plan.py` — `SheetRowPlanner` Haystack component → `SheetPlan`
- `app/services/agents/layout_hinter.py`
- `app/services/agents/plan_reviewer.py`
- `app/services/agents/field_namer.py`
- `app/prompts/workflow/layout_hinter.md`
- `app/prompts/workflow/plan_reviewer.md`
- `app/prompts/workflow/field_namer.md`
- `app/services/applier/apply_plan.py` — pure deterministic resolver
- `app/services/validation/plan_invariants.py` — Tier 1 plan validators
- `app/services/validation/plan_statistics.py` — Tier 2 plan validators

**Modified files:**
- `app/services/extraction.py` — rewrite orchestrator pipeline
- `app/services/applier/__init__.py` — expose `apply_plan`, drop old appliers
- `app/models/__init__.py` — export new artifact types
- `docs/SPEC.md`, `ARCHITECTURE.md`, `README.md` (final phase only, after tests + evals green)
- `docs/superpowers/specs/2026-05-13-sheet-row-planner-design.md` — flip Status to `Implemented` at the end

**Deleted files (last phase):**
- `app/services/agents/layout_fingerprinter.py`
- `app/services/agents/boundary_finder.py`
- `app/services/agents/identity_locator.py`
- `app/services/agents/quantity_date_locator.py`
- `app/services/agents/stage_locator.py`
- `app/services/applier/patterns/` (entire directory: `__init__.py`, `_registry.py` if specific, `one_row_per_pli.py`, `vertical_merge.py`, `data_then_total.py`, `one_sheet_per_pli.py`)
- `app/services/applier/_registry.py` (pattern registry, separate from tool registry)
- `app/services/applier/field_applier.py`
- `app/services/applier/stage_applier.py`
- `app/enums/boundary_pattern.py`
- `app/enums/stage_layout_mode.py`
- `app/prompts/workflow/layout_fingerprinter.md`
- `app/prompts/workflow/boundary_finder.md`
- `app/prompts/workflow/identity_locator.md`
- `app/prompts/workflow/quantity_date_locator.md`
- `app/prompts/workflow/stage_locator.md`

---

## Phase 1 — Foundation: enums and Pydantic artifacts

### Task 1: `PliMode` enum

**Files:**
- Create: `app/enums/pli_mode.py`
- Test: `tests/unit/enums/test_pli_mode.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/enums/test_pli_mode.py
from app.enums.pli_mode import PliMode


def test_pli_mode_values():
    assert PliMode.ROW_PER_PLI.value == "row_per_pli"
    assert PliMode.SECTION_PER_PLI.value == "section_per_pli"
    assert PliMode.SHEET_IS_PLI.value == "sheet_is_pli"


def test_pli_mode_members_count():
    assert len(list(PliMode)) == 3
```

- [ ] **Step 2: Run test, expect FAIL**

```
.venv/Scripts/python.exe -m pytest tests/unit/enums/test_pli_mode.py -q
```
Expected: `ModuleNotFoundError: No module named 'app.enums.pli_mode'`

- [ ] **Step 3: Implement**

```python
# app/enums/pli_mode.py
"""Whether a sheet contains one PLI per row, one PLI per section, or is itself one PLI."""
from __future__ import annotations
from enum import Enum


class PliMode(str, Enum):
    ROW_PER_PLI = "row_per_pli"
    SECTION_PER_PLI = "section_per_pli"
    SHEET_IS_PLI = "sheet_is_pli"
```

- [ ] **Step 4: Run test, expect PASS**

```
.venv/Scripts/python.exe -m pytest tests/unit/enums/test_pli_mode.py -q
```
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/enums/pli_mode.py tests/unit/enums/test_pli_mode.py
git commit -m "feat(enums): add PliMode (row_per_pli / section_per_pli / sheet_is_pli)"
```

---

### Task 2: `RowRole` and `SubRowRole` enums

**Files:**
- Create: `app/enums/row_role.py`
- Test: `tests/unit/enums/test_row_role.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/enums/test_row_role.py
from app.enums.row_role import RowRole, SubRowRole


def test_row_role_values():
    assert RowRole.TITLE.value == "title"
    assert RowRole.HEADER.value == "header"
    assert RowRole.ANCHOR.value == "anchor"
    assert RowRole.CHILD.value == "child"
    assert RowRole.TOTAL.value == "total"
    assert RowRole.GRAND_TOTAL.value == "grand_total"
    assert RowRole.REPEAT_HEADER.value == "repeat_header"
    assert RowRole.BLANK.value == "blank"
    assert RowRole.SEPARATOR.value == "separator"


def test_sub_row_role_values():
    assert SubRowRole.PLAN.value == "plan"
    assert SubRowRole.ACTION.value == "action"
    assert SubRowRole.ACTUAL.value == "actual"
    assert SubRowRole.DEVIATION.value == "deviation"
```

- [ ] **Step 2: Run test, expect FAIL**

```
.venv/Scripts/python.exe -m pytest tests/unit/enums/test_row_role.py -q
```

- [ ] **Step 3: Implement**

```python
# app/enums/row_role.py
"""Per-row classification for SheetPlan.

`RowRole` is what kind of row it is (data, header, total, etc.). `SubRowRole`
is which value layer the row represents within a multi-row PLI (plan vs action
vs deviation).
"""
from __future__ import annotations
from enum import Enum


class RowRole(str, Enum):
    TITLE = "title"
    HEADER = "header"
    ANCHOR = "anchor"
    CHILD = "child"
    TOTAL = "total"
    GRAND_TOTAL = "grand_total"
    REPEAT_HEADER = "repeat_header"
    BLANK = "blank"
    SEPARATOR = "separator"


class SubRowRole(str, Enum):
    PLAN = "plan"
    ACTION = "action"
    ACTUAL = "actual"
    DEVIATION = "deviation"
```

- [ ] **Step 4: Run test, expect PASS**

```
.venv/Scripts/python.exe -m pytest tests/unit/enums/test_row_role.py -q
```

- [ ] **Step 5: Commit**

```bash
git add app/enums/row_role.py tests/unit/enums/test_row_role.py
git commit -m "feat(enums): add RowRole and SubRowRole"
```

---

### Task 3: `StageScope` enum

**Files:**
- Create: `app/enums/stage_scope.py`
- Test: `tests/unit/enums/test_stage_scope.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/enums/test_stage_scope.py
from app.enums.stage_scope import StageScope


def test_stage_scope_values():
    assert StageScope.SHEET_LEVEL.value == "sheet_level"
    assert StageScope.SECTION_LOCAL.value == "section_local"
    assert StageScope.PLI_LOCAL.value == "pli_local"
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Implement**

```python
# app/enums/stage_scope.py
"""Where stage bands live relative to PLIs."""
from __future__ import annotations
from enum import Enum


class StageScope(str, Enum):
    SHEET_LEVEL = "sheet_level"
    SECTION_LOCAL = "section_local"
    PLI_LOCAL = "pli_local"
```

- [ ] **Step 4: Run test, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add app/enums/stage_scope.py tests/unit/enums/test_stage_scope.py
git commit -m "feat(enums): add StageScope (sheet/section/pli-local)"
```

---

### Task 4: New Pydantic artifacts — `SheetSignals`, `RowSpec`, `KVAnchor`

**Files:**
- Modify: `app/models/artifacts.py` (append new classes at the bottom)
- Test: `tests/unit/models/test_sheet_plan_artifacts.py`

- [ ] **Step 1: Write the failing test for `RowSpec`**

```python
# tests/unit/models/test_sheet_plan_artifacts.py
from app.models.artifacts import RowSpec, KVAnchor, SheetSignals
from app.enums.row_role import RowRole, SubRowRole


def test_row_spec_anchor():
    r = RowSpec(idx=4, role=RowRole.ANCHOR)
    assert r.idx == 4
    assert r.role is RowRole.ANCHOR
    assert r.anchor_idx is None
    assert r.group_id is None
    assert r.sub_row_role is None


def test_row_spec_child_with_anchor():
    r = RowSpec(idx=5, role=RowRole.CHILD, anchor_idx=4, group_id=0)
    assert r.anchor_idx == 4
    assert r.group_id == 0


def test_row_spec_sub_row_role():
    r = RowSpec(idx=3, role=RowRole.CHILD, anchor_idx=2,
                group_id=0, sub_row_role=SubRowRole.ACTION)
    assert r.sub_row_role is SubRowRole.ACTION


def test_kv_anchor():
    kv = KVAnchor(label_cell="A4", value_cell="B4", field="io_number")
    assert kv.label_cell == "A4"
    assert kv.value_cell == "B4"
    assert kv.field == "io_number"


def test_sheet_signals_minimal():
    s = SheetSignals(sheet="X", max_row=10, max_col=5,
                     merges=[], identity_col_candidates=["B"],
                     header_vocab_hits={"B": ["IO NO"]},
                     date_typed_cols=["D"], blank_run_gaps=[])
    assert s.sheet == "X"
    assert s.identity_col_candidates == ["B"]
```

- [ ] **Step 2: Run test, expect FAIL**

```
.venv/Scripts/python.exe -m pytest tests/unit/models/test_sheet_plan_artifacts.py -q
```

- [ ] **Step 3: Implement — append to `app/models/artifacts.py`**

Open `app/models/artifacts.py` and add at the bottom of the file:

```python
# --- SheetRowPlanner artifacts ---
from app.enums.row_role import RowRole, SubRowRole
from app.enums.pli_mode import PliMode
from app.enums.stage_scope import StageScope


class SheetSignals(BaseModel):
    """Raw structural signals collected by SheetSurveyor for a sheet."""
    model_config = ConfigDict(extra="ignore")
    sheet: str
    max_row: int
    max_col: int
    merges: list[tuple[int, int, int, int]] = Field(default_factory=list)
    identity_col_candidates: list[str] = Field(default_factory=list)
    header_vocab_hits: dict[str, list[str]] = Field(default_factory=dict)
    date_typed_cols: list[str] = Field(default_factory=list)
    blank_run_gaps: list[tuple[int, int]] = Field(default_factory=list)
    kv_label_hits: list[tuple[str, str]] = Field(default_factory=list)


class RowSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    idx: int
    role: RowRole
    anchor_idx: int | None = None
    group_id: int | None = None
    sub_row_role: SubRowRole | None = None


class KVAnchor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label_cell: str
    value_cell: str
    field: str
```

If `BaseModel`, `ConfigDict`, and `Field` are not imported at the top of `artifacts.py`, add them: `from pydantic import BaseModel, ConfigDict, Field`.

- [ ] **Step 4: Run test, expect PASS**

```
.venv/Scripts/python.exe -m pytest tests/unit/models/test_sheet_plan_artifacts.py -q
```
Expected: `4 passed` (the SheetSignals + 3 RowSpec/KVAnchor tests).

- [ ] **Step 5: Commit**

```bash
git add app/models/artifacts.py tests/unit/models/test_sheet_plan_artifacts.py
git commit -m "feat(artifacts): add SheetSignals, RowSpec, KVAnchor"
```

---

### Task 5: Pydantic artifacts — `StageBandSpec`, `PliBlock`, `SheetPlan`

**Files:**
- Modify: `app/models/artifacts.py` (append)
- Modify: `tests/unit/models/test_sheet_plan_artifacts.py` (extend)

- [ ] **Step 1: Add tests**

Append to `tests/unit/models/test_sheet_plan_artifacts.py`:

```python
from app.models.artifacts import StageBandSpec, PliBlock, SheetPlan


def test_stage_band_spec_minimal():
    sb = StageBandSpec(
        name="Pre-Prod", name_cell="A8", sub_header_row=8,
        sub_rows={"plan": 9, "action": 10},
        stage_cols={"L/D send": "C", "Fit send": "D"},
        layout_mode="tall_sub_rows",
    )
    assert sb.name == "Pre-Prod"
    assert sb.stage_cols["L/D send"] == "C"


def test_pli_block_with_identity_and_bands():
    kv = KVAnchor(label_cell="A4", value_cell="B4", field="io_number")
    sb = StageBandSpec(name="Pre-Prod", name_cell="A8", sub_header_row=8,
                       sub_rows={"plan": 9}, stage_cols={"X": "C"},
                       layout_mode="tall_sub_rows")
    blk = PliBlock(id=0, bbox=(3, 14), identity=[kv], stage_bands=[sb])
    assert blk.bbox == (3, 14)
    assert blk.identity[0].field == "io_number"
    assert blk.stage_bands[0].name == "Pre-Prod"


def test_sheet_plan_row_per_pli_minimal():
    plan = SheetPlan(
        sheet="X", pli_mode=PliMode.ROW_PER_PLI, identity_column="B",
        header_rows=[1], rows=[RowSpec(idx=2, role=RowRole.ANCHOR)],
        stage_scope=StageScope.SHEET_LEVEL, confidence=0.9,
    )
    assert plan.pli_mode is PliMode.ROW_PER_PLI
    assert plan.identity_column == "B"


def test_sheet_plan_sheet_is_pli_minimal():
    plan = SheetPlan(
        sheet="X", pli_mode=PliMode.SHEET_IS_PLI,
        header_rows=[], rows=[],
        kv_anchors=[KVAnchor(label_cell="A4", value_cell="B4", field="io_number")],
        stage_scope=StageScope.SHEET_LEVEL, confidence=0.95,
    )
    assert plan.pli_mode is PliMode.SHEET_IS_PLI
    assert plan.kv_anchors[0].field == "io_number"
```

- [ ] **Step 2: Run tests, expect FAIL for the 4 new tests**

```
.venv/Scripts/python.exe -m pytest tests/unit/models/test_sheet_plan_artifacts.py -q
```

- [ ] **Step 3: Implement — append to `app/models/artifacts.py`**

```python
class StageBandSpec(BaseModel):
    """Where one stage band lives on a sheet.

    `sub_rows` keys are SubRowRole values (str); `stage_cols` maps a stage's
    display name to its column letter.
    """
    model_config = ConfigDict(extra="ignore")
    name: str
    name_cell: str
    sub_header_row: int
    sub_rows: dict[str, int] = Field(default_factory=dict)
    stage_cols: dict[str, str] = Field(default_factory=dict)
    layout_mode: str = "wide_sub_columns"


class PliBlock(BaseModel):
    """A sub-rectangle of a sheet representing one PLI in SECTION_PER_PLI mode."""
    model_config = ConfigDict(extra="ignore")
    id: int
    bbox: tuple[int, int]
    identity: list[KVAnchor] = Field(default_factory=list)
    stage_bands: list[StageBandSpec] = Field(default_factory=list)


class SheetPlan(BaseModel):
    """The unified plan produced by SheetRowPlanner.

    `rows` is populated when pli_mode = ROW_PER_PLI.
    `pli_blocks` is populated when pli_mode = SECTION_PER_PLI.
    `kv_anchors` is populated when pli_mode = SHEET_IS_PLI (and also on hybrid
    sheets where workbook-header KV applies to every PLI emitted from `rows`).
    """
    model_config = ConfigDict(extra="ignore")
    sheet: str
    pli_mode: PliMode
    identity_column: str | None = None
    header_rows: list[int] = Field(default_factory=list)
    rows: list[RowSpec] = Field(default_factory=list)
    pli_blocks: list[PliBlock] = Field(default_factory=list)
    kv_anchors: list[KVAnchor] = Field(default_factory=list)
    stage_bands: list[StageBandSpec] = Field(default_factory=list)
    stage_scope: StageScope = StageScope.SHEET_LEVEL
    confidence: float = 1.0
```

- [ ] **Step 4: Run tests, expect PASS**

Expected: `8 passed` (4 from Task 4 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add app/models/artifacts.py tests/unit/models/test_sheet_plan_artifacts.py
git commit -m "feat(artifacts): add StageBandSpec, PliBlock, SheetPlan"
```

---

### Task 6: Pydantic artifacts — `CanonicalNameMap`, `LayoutHints`, `PlanVerdict`

**Files:**
- Modify: `app/models/artifacts.py`
- Modify: `tests/unit/models/test_sheet_plan_artifacts.py`

- [ ] **Step 1: Add tests**

Append to `tests/unit/models/test_sheet_plan_artifacts.py`:

```python
from app.models.artifacts import CanonicalNameMap, LayoutHints, PlanVerdict


def test_canonical_name_map():
    nm = CanonicalNameMap(
        field_labels={"Ex-Fty date": "delivery_date",
                      "Job No": "io_number"},
        stage_names={"L/D send": "lab_dip_send"},
    )
    assert nm.field_labels["Ex-Fty date"] == "delivery_date"


def test_layout_hints():
    h = LayoutHints(
        identity_column_suggestion="B",
        mode_suggestion="row_per_pli",
        notes=["B is clearly the IO column"],
    )
    assert h.identity_column_suggestion == "B"


def test_plan_verdict_looks_correct():
    v = PlanVerdict(verdict="looks_correct", row_corrections=[],
                    identity_column_suggestion=None, warnings=[],
                    confidence=0.95)
    assert v.verdict == "looks_correct"


def test_plan_verdict_needs_fix():
    v = PlanVerdict(
        verdict="needs_fix",
        row_corrections=[{"row": 8, "current_role": "total",
                          "suggested_role": "child", "anchor_idx": 4}],
        warnings=["stage band 'CUTTING' may start one column earlier"],
        confidence=0.85,
    )
    assert v.row_corrections[0]["row"] == 8
```

- [ ] **Step 2: Run tests, expect FAIL**

- [ ] **Step 3: Implement — append to `app/models/artifacts.py`**

```python
class CanonicalNameMap(BaseModel):
    """FieldNamer's output — map detected labels to canonical names."""
    model_config = ConfigDict(extra="ignore")
    field_labels: dict[str, str] = Field(default_factory=dict)
    stage_names: dict[str, str] = Field(default_factory=dict)


class LayoutHints(BaseModel):
    """LayoutHinter's output — disambiguation hints for the planner."""
    model_config = ConfigDict(extra="ignore")
    identity_column_suggestion: str | None = None
    mode_suggestion: str | None = None
    notes: list[str] = Field(default_factory=list)


class PlanVerdict(BaseModel):
    """PlanReviewer's output — judging a draft SheetPlan."""
    model_config = ConfigDict(extra="ignore")
    verdict: str = "looks_correct"
    row_corrections: list[dict] = Field(default_factory=list)
    identity_column_suggestion: str | None = None
    warnings: list[str] = Field(default_factory=list)
    confidence: float = 1.0
```

- [ ] **Step 4: Run tests, expect PASS**

- [ ] **Step 5: Update `app/models/__init__.py`**

Add to imports + `__all__`:

```python
from app.models.artifacts import (
    # … existing names …
    SheetSignals, RowSpec, KVAnchor, StageBandSpec, PliBlock, SheetPlan,
    CanonicalNameMap, LayoutHints, PlanVerdict,
)
```

Add the same names to `__all__`.

- [ ] **Step 6: Run full test suite to confirm nothing regressed**

```
.venv/Scripts/python.exe -m pytest tests -q
```
Expected: all currently-passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add app/models/artifacts.py app/models/__init__.py tests/unit/models/test_sheet_plan_artifacts.py
git commit -m "feat(artifacts): add CanonicalNameMap, LayoutHints, PlanVerdict"
```

---

## Phase 2 — Planner deterministic core

### Task 7: `SheetSurveyor` — collect raw signals

**Files:**
- Create: `app/services/planner/__init__.py` (empty)
- Create: `app/services/planner/surveyor.py`
- Test: `tests/unit/planner/test_surveyor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/planner/test_surveyor.py
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.services.planner.surveyor import survey_sheet


def test_survey_basic_grid(tmp_path):
    clear_cache()
    wb = Workbook(); ws = wb.active
    ws.title = "S"
    ws["A1"] = "IO NO"; ws["B1"] = "STYLE"; ws["C1"] = "QTY"
    ws["A2"] = 1063;    ws["B2"] = "DWJE"; ws["C2"] = 2356
    ws["A3"] = 1064;    ws["B3"] = "DWJF"; ws["C3"] = 1500
    p = tmp_path / "x.xlsx"; wb.save(p)
    ctx = register_workbook(p)
    sig = survey_sheet(ctx, "S")
    assert sig.sheet == "S"
    assert sig.max_row == 3
    assert "A" in sig.identity_col_candidates  # "IO NO" matches
    assert "IO NO" in sig.header_vocab_hits.get("A", [])


def test_survey_detects_merges(tmp_path):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    ws["A1"] = "IO"; ws["A2"] = 1063
    ws.merge_cells("A2:A4")
    p = tmp_path / "x.xlsx"; wb.save(p)
    ctx = register_workbook(p)
    sig = survey_sheet(ctx, "S")
    assert (2, 1, 4, 1) in sig.merges


def test_survey_detects_blank_run_gap(tmp_path):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    ws["A1"] = "IO"
    ws["A2"] = 1063; ws["A3"] = 1064
    # rows 4, 5 entirely empty
    ws["A6"] = 1065
    p = tmp_path / "x.xlsx"; wb.save(p)
    ctx = register_workbook(p)
    sig = survey_sheet(ctx, "S")
    assert (4, 5) in sig.blank_run_gaps


def test_survey_detects_kv_label_hits(tmp_path):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    ws["A1"] = "Job No"; ws["B1"] = 63315
    ws["A2"] = "Quantity"; ws["B2"] = 254886
    p = tmp_path / "x.xlsx"; wb.save(p)
    ctx = register_workbook(p)
    sig = survey_sheet(ctx, "S")
    labels = {x[0] for x in sig.kv_label_hits}
    assert "Job No" in labels and "Quantity" in labels
```

- [ ] **Step 2: Run tests, expect FAIL**

- [ ] **Step 3: Implement**

```python
# app/services/planner/surveyor.py
"""Deterministic single-pass survey of a sheet — collects raw structural signals
that downstream planner components consume.
"""
from __future__ import annotations
from datetime import date, datetime
from openpyxl.utils import get_column_letter
from app.models.workbook import WorkbookCtx
from app.models.artifacts import SheetSignals


# Identity-column header vocabulary (case-insensitive substring match).
_IDENTITY_VOCAB = (
    "io no", "io number", "io",
    "job no", "job number",
    "po no", "po number", "buyer po", "buyer po no",
    "style no", "style code", "style",
)

# KV-label vocabulary — labels found in scattered KV identity blocks.
_KV_LABEL_VOCAB = (
    "job no", "io no", "io number", "po no", "buyer po no",
    "quantity", "qty", "order qty", "plan qty",
    "ex-fac date", "ex-fty date", "ex fac date", "ex factory",
    "delivery date", "order receipt", "shipment date",
    "style", "fabric", "color", "colour",
)


def _norm(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


def survey_sheet(ctx: WorkbookCtx, sheet: str) -> SheetSignals:
    ws = ctx.wb[sheet]
    max_row = ws.max_row or 0
    max_col = ws.max_column or 0

    merges: list[tuple[int, int, int, int]] = [
        (mr.min_row, mr.min_col, mr.max_row, mr.max_col)
        for mr in ws.merged_cells.ranges
    ]

    # Pass 1: scan up to first 15 rows for header vocabulary + KV labels.
    header_vocab_hits: dict[str, list[str]] = {}
    kv_label_hits: list[tuple[str, str]] = []
    for r in range(1, min(max_row, 15) + 1):
        for c in range(1, max_col + 1):
            v = ws.cell(row=r, column=c).value
            if not isinstance(v, str):
                continue
            v_norm = _norm(v)
            col_letter = get_column_letter(c)
            if any(term in v_norm for term in _IDENTITY_VOCAB):
                header_vocab_hits.setdefault(col_letter, []).append(v)
            if any(term == v_norm or v_norm.endswith(term) or v_norm.startswith(term)
                   for term in _KV_LABEL_VOCAB):
                kv_label_hits.append((v, f"{col_letter}{r}"))

    identity_col_candidates = list(header_vocab_hits.keys())

    # Pass 2: detect blank-run gaps inside the data region.
    blank_run_gaps: list[tuple[int, int]] = []
    run_start: int | None = None
    for r in range(1, max_row + 1):
        row_empty = all(
            ws.cell(row=r, column=c).value is None
            for c in range(1, max_col + 1)
        )
        if row_empty and run_start is None:
            run_start = r
        elif not row_empty and run_start is not None:
            if r - 1 >= run_start:
                blank_run_gaps.append((run_start, r - 1))
            run_start = None
    if run_start is not None and max_row >= run_start:
        blank_run_gaps.append((run_start, max_row))

    # Pass 3: detect date-typed columns.
    date_typed_cols: list[str] = []
    for c in range(1, max_col + 1):
        seen = 0
        date_count = 0
        for r in range(1, max_row + 1):
            v = ws.cell(row=r, column=c).value
            if v is None:
                continue
            seen += 1
            if isinstance(v, (date, datetime)):
                date_count += 1
        if seen >= 2 and date_count / seen >= 0.5:
            date_typed_cols.append(get_column_letter(c))

    return SheetSignals(
        sheet=sheet, max_row=max_row, max_col=max_col,
        merges=merges,
        identity_col_candidates=identity_col_candidates,
        header_vocab_hits=header_vocab_hits,
        date_typed_cols=date_typed_cols,
        blank_run_gaps=blank_run_gaps,
        kv_label_hits=kv_label_hits,
    )
```

- [ ] **Step 4: Run tests, expect PASS**

```
.venv/Scripts/python.exe -m pytest tests/unit/planner/test_surveyor.py -q
```
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/services/planner/__init__.py app/services/planner/surveyor.py tests/unit/planner/test_surveyor.py
git commit -m "feat(planner): SheetSurveyor — collect raw structural signals"
```

---

### Task 8: `row_classifier` — assign a `RowRole` to each row

**Files:**
- Create: `app/services/planner/row_classifier.py`
- Test: `tests/unit/planner/test_row_classifier.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/planner/test_row_classifier.py
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.services.planner.surveyor import survey_sheet
from app.services.planner.row_classifier import classify_rows
from app.enums.row_role import RowRole


def _ctx_from(tmp_path, cells: dict[str, object], merges: list[str] | None = None):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    for addr, val in cells.items():
        ws[addr] = val
    for mr in (merges or []):
        ws.merge_cells(mr)
    p = tmp_path / "x.xlsx"; wb.save(p)
    return register_workbook(p)


def test_classify_anchor_and_children(tmp_path):
    ctx = _ctx_from(
        tmp_path,
        {"A1": "IO NO", "B1": "COLOR",
         "A2": 1063, "B2": "MAGENTA",
         "B3": "NAVY", "B4": "WHITE"},
        merges=["A2:A4"],
    )
    sig = survey_sheet(ctx, "S")
    rows = classify_rows(ctx, "S", sig, identity_column="A")
    by_idx = {r.idx: r for r in rows}
    assert by_idx[1].role is RowRole.HEADER
    assert by_idx[2].role is RowRole.ANCHOR
    assert by_idx[3].role is RowRole.CHILD
    assert by_idx[3].anchor_idx == 2
    assert by_idx[4].role is RowRole.CHILD
    assert by_idx[4].anchor_idx == 2


def test_classify_total_via_sum_of_children(tmp_path):
    ctx = _ctx_from(
        tmp_path,
        {"A1": "IO NO", "C1": "QTY",
         "A2": 1063, "C2": 1000,
         "A3": 1064, "C3": 2000,
         "C4": 3000},  # row 4 is a total: 1000 + 2000 = 3000
    )
    sig = survey_sheet(ctx, "S")
    rows = classify_rows(ctx, "S", sig, identity_column="A",
                        quantity_column_hint="C")
    by_idx = {r.idx: r for r in rows}
    assert by_idx[4].role is RowRole.TOTAL


def test_classify_blank_row(tmp_path):
    ctx = _ctx_from(
        tmp_path,
        {"A1": "IO NO", "A2": 1063, "A4": 1064},  # row 3 entirely blank
    )
    sig = survey_sheet(ctx, "S")
    rows = classify_rows(ctx, "S", sig, identity_column="A")
    by_idx = {r.idx: r for r in rows}
    assert by_idx[3].role is RowRole.BLANK


def test_classify_repeat_header(tmp_path):
    ctx = _ctx_from(
        tmp_path,
        {"A1": "IO NO", "A2": 1063, "A3": "IO NO", "A4": 1064},
    )
    sig = survey_sheet(ctx, "S")
    rows = classify_rows(ctx, "S", sig, identity_column="A")
    by_idx = {r.idx: r for r in rows}
    assert by_idx[3].role is RowRole.REPEAT_HEADER
```

- [ ] **Step 2: Run tests, expect FAIL**

- [ ] **Step 3: Implement**

```python
# app/services/planner/row_classifier.py
"""Classify each row of a sheet into a RowRole.

Rules (in priority order):
  1. Row is entirely empty → BLANK.
  2. Row sits in the header band (rows 1..first_data_row-1) and contains
     vocabulary terms → HEADER.
  3. Row's identity-column value matches a known header term → REPEAT_HEADER.
  4. Row's identity column has a value (directly or via merge anchor) AND
     it's not previously identified as a child of a prior anchor → ANCHOR.
  5. Row's identity column is empty AND sits inside a merge whose anchor
     has identity AND that anchor is in the data range → CHILD.
  6. Row's identity column is empty AND not in any identity merge AND the
     row's quantity column value equals the sum of recent ANCHOR+CHILD
     rows' quantity values → TOTAL.
  7. Otherwise → BLANK (unclassified row, dropped from data iteration).
"""
from __future__ import annotations
from openpyxl.utils import column_index_from_string, get_column_letter
from app.models.workbook import WorkbookCtx
from app.models.artifacts import SheetSignals, RowSpec
from app.enums.row_role import RowRole


def _norm(v: object) -> str:
    return "" if v is None else " ".join(str(v).strip().lower().split())


def classify_rows(
    ctx: WorkbookCtx,
    sheet: str,
    signals: SheetSignals,
    identity_column: str | None,
    quantity_column_hint: str | None = None,
) -> list[RowSpec]:
    ws = ctx.wb[sheet]
    rows: list[RowSpec] = []
    if identity_column is None:
        for r in range(1, signals.max_row + 1):
            rows.append(RowSpec(idx=r, role=RowRole.BLANK))
        return rows

    id_col = column_index_from_string(identity_column)
    qty_col = column_index_from_string(quantity_column_hint) if quantity_column_hint else None

    # Build a map: row → (merge_min_row, merge_min_col) for any merge containing identity-col cell.
    merge_anchor_of: dict[int, tuple[int, int]] = {}
    for (r1, c1, r2, c2) in signals.merges:
        if c1 <= id_col <= c2:
            for r in range(r1, r2 + 1):
                merge_anchor_of[r] = (r1, c1)

    header_vocab_set = {
        _norm(h)
        for hits in signals.header_vocab_hits.values()
        for h in hits
    }

    first_data_row: int | None = None
    last_known_anchor: int | None = None
    last_known_anchor_group: int | None = None
    next_group_id = 0
    recent_qtys: list[tuple[int, float]] = []  # (group_id, qty)

    for r in range(1, signals.max_row + 1):
        row_blank = all(
            ws.cell(row=r, column=c).value is None
            for c in range(1, signals.max_col + 1)
        )
        if row_blank:
            rows.append(RowSpec(idx=r, role=RowRole.BLANK))
            continue

        id_val = ws.cell(row=r, column=id_col).value
        merged = merge_anchor_of.get(r)
        merge_anchor_value = (
            ws.cell(row=merged[0], column=merged[1]).value if merged else None
        )

        # HEADER detection: above any data row.
        if first_data_row is None:
            row_strs = [
                _norm(ws.cell(row=r, column=c).value)
                for c in range(1, signals.max_col + 1)
                if isinstance(ws.cell(row=r, column=c).value, str)
            ]
            if any(s in header_vocab_set for s in row_strs):
                rows.append(RowSpec(idx=r, role=RowRole.HEADER))
                continue

        # REPEAT_HEADER detection: identity column has a string that is a known header term.
        if isinstance(id_val, str) and _norm(id_val) in header_vocab_set:
            rows.append(RowSpec(idx=r, role=RowRole.REPEAT_HEADER))
            continue

        # ANCHOR: identity column populated directly.
        if id_val is not None and (merged is None or merged[0] == r):
            if first_data_row is None:
                first_data_row = r
            last_known_anchor = r
            last_known_anchor_group = next_group_id
            next_group_id += 1
            rows.append(RowSpec(idx=r, role=RowRole.ANCHOR,
                               group_id=last_known_anchor_group))
            if qty_col:
                q = ws.cell(row=r, column=qty_col).value
                if isinstance(q, (int, float)):
                    recent_qtys.append((last_known_anchor_group, float(q)))
            continue

        # CHILD: identity blank but inside a merge whose anchor has identity.
        if id_val is None and merged is not None and merge_anchor_value is not None and last_known_anchor is not None:
            rows.append(RowSpec(idx=r, role=RowRole.CHILD,
                               anchor_idx=last_known_anchor,
                               group_id=last_known_anchor_group))
            if qty_col:
                q = ws.cell(row=r, column=qty_col).value
                if isinstance(q, (int, float)):
                    recent_qtys.append((last_known_anchor_group, float(q)))
            continue

        # TOTAL: identity blank, no merge, qty column matches sum of recent rows.
        if qty_col is not None and id_val is None:
            q = ws.cell(row=r, column=qty_col).value
            if isinstance(q, (int, float)):
                target = float(q)
                # Try: sum of recent group, then all recent groups (grand total).
                if last_known_anchor_group is not None:
                    group_sum = sum(
                        v for g, v in recent_qtys
                        if g == last_known_anchor_group
                    )
                    if abs(group_sum - target) < 0.5:
                        rows.append(RowSpec(idx=r, role=RowRole.TOTAL))
                        continue
                grand_sum = sum(v for _, v in recent_qtys)
                if abs(grand_sum - target) < 0.5:
                    rows.append(RowSpec(idx=r, role=RowRole.GRAND_TOTAL))
                    continue

        rows.append(RowSpec(idx=r, role=RowRole.BLANK))

    return rows
```

- [ ] **Step 4: Run tests, expect PASS**

```
.venv/Scripts/python.exe -m pytest tests/unit/planner/test_row_classifier.py -q
```
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/services/planner/row_classifier.py tests/unit/planner/test_row_classifier.py
git commit -m "feat(planner): row_classifier — classify rows into anchor/child/total/etc."
```

---

### Task 9: `kv_anchor_detector` — find scattered label→value pairs

**Files:**
- Create: `app/services/planner/kv_anchor_detector.py`
- Test: `tests/unit/planner/test_kv_anchor_detector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/planner/test_kv_anchor_detector.py
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.services.planner.surveyor import survey_sheet
from app.services.planner.kv_anchor_detector import detect_kv_anchors


def _ctx(tmp_path, cells):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    for addr, val in cells.items():
        ws[addr] = val
    p = tmp_path / "x.xlsx"; wb.save(p)
    return register_workbook(p)


def test_kv_label_value_horizontal(tmp_path):
    ctx = _ctx(tmp_path, {
        "A3": "Date :", "B3": "2026-04-17",
        "A4": "Job No", "B4": 63315,
        "A5": "Quantity", "B5": 254886,
    })
    sig = survey_sheet(ctx, "S")
    kvs = detect_kv_anchors(ctx, "S", sig)
    by_lbl = {k.label_cell: k for k in kvs}
    assert by_lbl["A4"].value_cell == "B4"
    assert by_lbl["A5"].value_cell == "B5"


def test_kv_label_value_vertical(tmp_path):
    """Some sheets put labels above values rather than to the left."""
    ctx = _ctx(tmp_path, {
        "A3": "Job No", "A4": 63315,
        "B3": "Quantity", "B4": 254886,
    })
    sig = survey_sheet(ctx, "S")
    kvs = detect_kv_anchors(ctx, "S", sig)
    by_lbl = {k.label_cell: k for k in kvs}
    assert by_lbl["A3"].value_cell == "A4"
    assert by_lbl["B3"].value_cell == "B4"


def test_kv_skip_when_no_adjacent_value(tmp_path):
    ctx = _ctx(tmp_path, {"A1": "Job No"})  # nothing in B1 or A2
    sig = survey_sheet(ctx, "S")
    kvs = detect_kv_anchors(ctx, "S", sig)
    assert kvs == []
```

- [ ] **Step 2: Run tests, expect FAIL**

- [ ] **Step 3: Implement**

```python
# app/services/planner/kv_anchor_detector.py
"""Detect scattered key-value identity blocks (Family 5 layouts).

For each label cell flagged by SheetSurveyor, look at (row, col+1) and
(row+1, col). If exactly one is non-empty and the other is empty (or both
are non-empty but the offset+1 cell is clearly a value), prefer (0,+1).
"""
from __future__ import annotations
from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.utils.cell import coordinate_from_string
from app.models.workbook import WorkbookCtx
from app.models.artifacts import SheetSignals, KVAnchor


def detect_kv_anchors(
    ctx: WorkbookCtx, sheet: str, signals: SheetSignals,
) -> list[KVAnchor]:
    ws = ctx.wb[sheet]
    out: list[KVAnchor] = []
    for label, addr in signals.kv_label_hits:
        col_letter, row = coordinate_from_string(addr)
        col = column_index_from_string(col_letter)
        right = ws.cell(row=row, column=col + 1).value if col + 1 <= signals.max_col else None
        below = ws.cell(row=row + 1, column=col).value if row + 1 <= signals.max_row else None

        if right is not None and not isinstance(right, str):
            out.append(KVAnchor(
                label_cell=addr,
                value_cell=f"{get_column_letter(col + 1)}{row}",
                field=label,
            ))
        elif right is not None and isinstance(right, str) and below is None:
            out.append(KVAnchor(
                label_cell=addr,
                value_cell=f"{get_column_letter(col + 1)}{row}",
                field=label,
            ))
        elif below is not None:
            out.append(KVAnchor(
                label_cell=addr,
                value_cell=f"{get_column_letter(col)}{row + 1}",
                field=label,
            ))
    return out
```

- [ ] **Step 4: Run tests, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add app/services/planner/kv_anchor_detector.py tests/unit/planner/test_kv_anchor_detector.py
git commit -m "feat(planner): kv_anchor_detector — scattered KV blocks"
```

---

### Task 10: `stage_band_detector` — find stage-band rectangles

**Files:**
- Create: `app/services/planner/stage_band_detector.py`
- Test: `tests/unit/planner/test_stage_band_detector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/planner/test_stage_band_detector.py
from datetime import datetime
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.services.planner.surveyor import survey_sheet
from app.services.planner.stage_band_detector import detect_stage_bands


def _ctx(tmp_path, cells):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    for addr, val in cells.items():
        ws[addr] = val
    p = tmp_path / "x.xlsx"; wb.save(p)
    return register_workbook(p)


def test_detect_tall_sub_rows_band(tmp_path):
    """Sheet with one stage band 'Pre-Prod' covering rows 8-11
    (header row, plan row, action row, deviation row)."""
    ctx = _ctx(tmp_path, {
        "A8": "Pre-Prod TNA",
        "C8": "L/D send", "D8": "Fit send", "E8": "AW send",
        "B9": "Plan",
        "C9": datetime(2026, 3, 1),
        "D9": datetime(2026, 3, 5),
        "E9": datetime(2026, 3, 10),
        "B10": "Action",
        "C10": datetime(2026, 3, 3),
        "B11": "Deviation",
    })
    sig = survey_sheet(ctx, "S")
    bands = detect_stage_bands(ctx, "S", sig)
    assert len(bands) == 1
    band = bands[0]
    assert band.name == "Pre-Prod TNA"
    assert band.name_cell == "A8"
    assert band.sub_rows.get("plan") == 9
    assert band.sub_rows.get("action") == 10
    assert band.sub_rows.get("deviation") == 11
    assert "L/D send" in band.stage_cols
    assert band.layout_mode == "tall_sub_rows"


def test_detect_wide_sub_columns_band(tmp_path):
    """Tabular sheet where stage 'Trims Inhouse' has primary (planned) and
    'actual' columns side-by-side, with data starting at row 4."""
    ctx = _ctx(tmp_path, {
        "R2": "Trims Inhouse",
        "R3": "Plan", "S3": "Actual",
        "R4": datetime(2026, 3, 25),
        "S4": datetime(2026, 3, 26),
        "R5": datetime(2026, 4, 1),
        "S5": datetime(2026, 4, 2),
    })
    sig = survey_sheet(ctx, "S")
    bands = detect_stage_bands(ctx, "S", sig)
    # We expect at least one detected band whose name_cell is R2.
    assert any(b.name_cell == "R2" and b.layout_mode == "wide_sub_columns"
               for b in bands)
```

- [ ] **Step 2: Run tests, expect FAIL**

- [ ] **Step 3: Implement**

```python
# app/services/planner/stage_band_detector.py
"""Detect stage-band rectangles on a sheet.

Two layout modes:
- WIDE_SUB_COLUMNS: stage name in row N, sub-headers (plan/actual) in row N+1,
  data rows below. One column per stage's primary + zero or more sub-cols.
- TALL_SUB_ROWS: stage names spread across columns in a single 'sub_header_row',
  with a left-of-band label column (column B typically) holding sub-row roles
  like 'Plan' / 'Action' / 'Deviation' for the rows below the header.
"""
from __future__ import annotations
from datetime import date, datetime
from openpyxl.utils import column_index_from_string, get_column_letter
from app.models.workbook import WorkbookCtx
from app.models.artifacts import SheetSignals, StageBandSpec


_SUB_ROW_LABELS = {"plan": "plan", "action": "action",
                   "actual": "actual", "actl": "actual",
                   "deviation": "deviation", "dev": "deviation"}


def _is_date(v: object) -> bool:
    return isinstance(v, (date, datetime))


def detect_stage_bands(
    ctx: WorkbookCtx, sheet: str, signals: SheetSignals,
) -> list[StageBandSpec]:
    ws = ctx.wb[sheet]
    bands: list[StageBandSpec] = []
    seen_name_cells: set[str] = set()

    # Sweep rows looking for runs of date-typed columns to the right; each run
    # rooted at row r implies a stage band whose sub_header_row is r-1 or r-2.
    for r in range(1, signals.max_row + 1):
        date_cols: list[int] = []
        for c in range(1, signals.max_col + 1):
            if _is_date(ws.cell(row=r, column=c).value):
                date_cols.append(c)
        if len(date_cols) < 2:
            continue

        # Walk back to find a row whose values are mostly strings — the sub_header.
        sub_header_row = None
        for prev in (r - 1, r - 2):
            if prev < 1:
                break
            str_count = sum(
                1 for c in date_cols
                if isinstance(ws.cell(row=prev, column=c).value, str)
            )
            if str_count >= max(2, len(date_cols) // 2):
                sub_header_row = prev
                break
        if sub_header_row is None:
            continue

        stage_cols: dict[str, str] = {}
        for c in date_cols:
            name = ws.cell(row=sub_header_row, column=c).value
            if isinstance(name, str) and name.strip():
                stage_cols[name.strip()] = get_column_letter(c)

        if not stage_cols:
            continue

        # Look one row above sub_header_row for a section title (in left column).
        title_row = sub_header_row - 1 if sub_header_row >= 2 else sub_header_row
        section_title = None
        name_cell = f"{get_column_letter(1)}{title_row}"
        for c in range(1, signals.max_col + 1):
            v = ws.cell(row=title_row, column=c).value
            if isinstance(v, str) and v.strip():
                section_title = v.strip()
                name_cell = f"{get_column_letter(c)}{title_row}"
                break
        if section_title is None:
            section_title = ws.cell(row=sub_header_row, column=1).value or "stage_band"
            section_title = str(section_title).strip()

        if name_cell in seen_name_cells:
            continue
        seen_name_cells.add(name_cell)

        # Determine layout: tall_sub_rows if the left col holds plan/action/etc. labels.
        sub_rows: dict[str, int] = {}
        for probe in range(r, min(signals.max_row, r + 5) + 1):
            label = ws.cell(row=probe, column=2).value
            if not isinstance(label, str):
                # fallback: try col 1
                label = ws.cell(row=probe, column=1).value
            if isinstance(label, str):
                key = _SUB_ROW_LABELS.get(label.strip().lower())
                if key:
                    sub_rows.setdefault(key, probe)

        if sub_rows:
            layout_mode = "tall_sub_rows"
            if "plan" not in sub_rows:
                sub_rows["plan"] = r
        else:
            layout_mode = "wide_sub_columns"
            sub_rows = {"plan": r}

        bands.append(StageBandSpec(
            name=section_title,
            name_cell=name_cell,
            sub_header_row=sub_header_row,
            sub_rows=sub_rows,
            stage_cols=stage_cols,
            layout_mode=layout_mode,
        ))

    return bands
```

- [ ] **Step 4: Run tests, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add app/services/planner/stage_band_detector.py tests/unit/planner/test_stage_band_detector.py
git commit -m "feat(planner): stage_band_detector — find stage rectangles"
```

---

### Task 11: `block_segmenter` — segment SECTION_PER_PLI blocks

**Files:**
- Create: `app/services/planner/block_segmenter.py`
- Test: `tests/unit/planner/test_block_segmenter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/planner/test_block_segmenter.py
from app.models.artifacts import SheetSignals, RowSpec, KVAnchor
from app.enums.row_role import RowRole
from app.services.planner.block_segmenter import segment_blocks


def test_segment_two_blocks_separated_by_blank_run():
    rows = [
        RowSpec(idx=1, role=RowRole.TITLE),
        RowSpec(idx=4, role=RowRole.ANCHOR, group_id=0),
        RowSpec(idx=7, role=RowRole.BLANK),
        RowSpec(idx=8, role=RowRole.BLANK),
        RowSpec(idx=9, role=RowRole.ANCHOR, group_id=1),
        RowSpec(idx=12, role=RowRole.BLANK),
    ]
    kvs = [
        KVAnchor(label_cell="A4", value_cell="B4", field="io_number"),
        KVAnchor(label_cell="A9", value_cell="B9", field="io_number"),
    ]
    blocks = segment_blocks(rows, kvs, blank_run_gaps=[(7, 8), (12, 12)])
    assert len(blocks) == 2
    assert blocks[0].bbox == (4, 6)
    assert blocks[1].bbox == (9, 11)


def test_segment_no_blocks_when_no_anchors():
    blocks = segment_blocks([], [], [])
    assert blocks == []
```

- [ ] **Step 2: Run tests, expect FAIL**

- [ ] **Step 3: Implement**

```python
# app/services/planner/block_segmenter.py
"""Segment a sheet into PliBlocks for SECTION_PER_PLI layouts.

Each block is bounded by blank-run gaps. Identity (KV anchors falling inside
the block's bbox) and stage bands (also inside the bbox) are attached.
"""
from __future__ import annotations
from app.models.artifacts import RowSpec, KVAnchor, PliBlock, StageBandSpec
from app.enums.row_role import RowRole
from openpyxl.utils.cell import coordinate_from_string


def _row_of(addr: str) -> int:
    _, r = coordinate_from_string(addr)
    return r


def segment_blocks(
    rows: list[RowSpec],
    kv_anchors: list[KVAnchor],
    blank_run_gaps: list[tuple[int, int]],
    stage_bands: list[StageBandSpec] | None = None,
) -> list[PliBlock]:
    stage_bands = stage_bands or []
    anchors = [r for r in rows if r.role is RowRole.ANCHOR]
    if not anchors:
        return []

    sorted_gaps = sorted(blank_run_gaps)
    blocks: list[PliBlock] = []
    block_id = 0
    for i, anc in enumerate(anchors):
        start = anc.idx
        end = anchors[i + 1].idx - 1 if i + 1 < len(anchors) else None
        for g_start, g_end in sorted_gaps:
            if g_start >= start and (end is None or g_start <= end):
                end = g_start - 1
                break
        if end is None:
            end = start

        block_kvs = [
            kv for kv in kv_anchors
            if start <= _row_of(kv.label_cell) <= end
        ]
        block_bands = [
            sb for sb in stage_bands
            if start <= _row_of(sb.name_cell) <= end
        ]
        blocks.append(PliBlock(
            id=block_id, bbox=(start, end),
            identity=block_kvs, stage_bands=block_bands,
        ))
        block_id += 1
    return blocks
```

- [ ] **Step 4: Run tests, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add app/services/planner/block_segmenter.py tests/unit/planner/test_block_segmenter.py
git commit -m "feat(planner): block_segmenter — SECTION_PER_PLI blocks"
```

---

### Task 12: `SheetRowPlanner` — the orchestrating component

**Files:**
- Create: `app/services/planner/plan.py`
- Test: `tests/unit/planner/test_plan.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/planner/test_plan.py
from datetime import datetime
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.services.planner.plan import SheetRowPlanner
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole


def _save(tmp_path, fn):
    wb = Workbook(); ws = wb.active; ws.title = "S"
    fn(ws)
    p = tmp_path / "x.xlsx"; wb.save(p)
    return p


def test_plan_row_per_pli_tabular(tmp_path):
    clear_cache()
    def fill(ws):
        ws["A1"] = "IO NO"; ws["B1"] = "STYLE"
        ws["A2"] = 1063; ws["B2"] = "DWJE"
        ws["A3"] = 1064; ws["B3"] = "DWJF"
    p = _save(tmp_path, fill)
    ctx = register_workbook(p)
    plan = SheetRowPlanner().run(workbook_ctx=ctx, sheet="S")["plan"]
    assert plan.pli_mode is PliMode.ROW_PER_PLI
    assert plan.identity_column == "A"
    anchors = [r for r in plan.rows if r.role is RowRole.ANCHOR]
    assert len(anchors) == 2


def test_plan_sheet_is_pli(tmp_path):
    clear_cache()
    def fill(ws):
        ws["A3"] = "Job No"; ws["B3"] = 63315
        ws["A4"] = "Quantity"; ws["B4"] = 254886
        # Stage band
        ws["A8"] = "Pre-Prod TNA"
        ws["C8"] = "L/D send"; ws["D8"] = "Fit send"
        ws["B9"] = "Plan"
        ws["C9"] = datetime(2026, 3, 1); ws["D9"] = datetime(2026, 3, 5)
    p = _save(tmp_path, fill)
    ctx = register_workbook(p)
    plan = SheetRowPlanner().run(workbook_ctx=ctx, sheet="S")["plan"]
    assert plan.pli_mode is PliMode.SHEET_IS_PLI
    assert len(plan.kv_anchors) >= 2
    assert len(plan.stage_bands) >= 1


def test_plan_christian_berg_like(tmp_path):
    """7 PLIs: 2 anchors + 5 children in 2 groups separated by totals."""
    clear_cache()
    def fill(ws):
        ws["A1"] = "S NO"; ws["B1"] = "IO NO"; ws["K1"] = "COLOR"; ws["L1"] = "ORDER QTY"
        ws["A2"] = 1; ws["B2"] = 1063; ws["K2"] = "MAGENTA"; ws["L2"] = 2356
        ws["K3"] = "NAVY"; ws["L3"] = 2356
        ws["K4"] = "WHITE"; ws["L4"] = 2356
        ws["K5"] = "DEEPTAUPE"; ws["L5"] = 2356
        ws["L6"] = 9424  # total row
        ws["A7"] = 2; ws["B7"] = 1064; ws["K7"] = "NAVY-OW"; ws["L7"] = 2050
        ws["K8"] = "SMOKE"; ws["L8"] = 1576
        ws["L9"] = 3626
        ws.merge_cells("A2:A5"); ws.merge_cells("B2:B5")
        ws.merge_cells("A7:A8"); ws.merge_cells("B7:B8")
    p = _save(tmp_path, fill)
    ctx = register_workbook(p)
    plan = SheetRowPlanner().run(workbook_ctx=ctx, sheet="S")["plan"]
    anchors = [r for r in plan.rows if r.role is RowRole.ANCHOR]
    children = [r for r in plan.rows if r.role is RowRole.CHILD]
    totals = [r for r in plan.rows if r.role is RowRole.TOTAL]
    assert len(anchors) == 2
    assert len(children) == 5
    assert len(totals) == 2
```

- [ ] **Step 2: Run tests, expect FAIL**

- [ ] **Step 3: Implement**

```python
# app/services/planner/plan.py
"""SheetRowPlanner — deterministic component producing a SheetPlan per sheet.

Composes SheetSurveyor, row_classifier, kv_anchor_detector, stage_band_detector,
and block_segmenter. Decides pli_mode from the collected signals.
"""
from __future__ import annotations
from typing import Any
from haystack import component
from app.models.artifacts import (
    SheetPlan, SheetSignals, RowSpec, KVAnchor, StageBandSpec, PliBlock,
)
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.services.planner.surveyor import survey_sheet
from app.services.planner.row_classifier import classify_rows
from app.services.planner.kv_anchor_detector import detect_kv_anchors
from app.services.planner.stage_band_detector import detect_stage_bands
from app.services.planner.block_segmenter import segment_blocks


def _decide_pli_mode(signals: SheetSignals) -> PliMode:
    has_identity_col = len(signals.identity_col_candidates) >= 1
    n_kv_hits = len(signals.kv_label_hits)
    n_blank_gaps = len(signals.blank_run_gaps)

    if has_identity_col:
        # If there are also many blank-run gaps AND no strong tabular grid,
        # SECTION_PER_PLI is plausible. Default to ROW_PER_PLI otherwise.
        if n_blank_gaps >= 2 and n_kv_hits >= 3:
            return PliMode.SECTION_PER_PLI
        return PliMode.ROW_PER_PLI
    if n_kv_hits >= 3:
        return PliMode.SHEET_IS_PLI
    return PliMode.ROW_PER_PLI  # fallback


def _pick_identity_column(signals: SheetSignals) -> str | None:
    if not signals.identity_col_candidates:
        return None
    # Prefer candidates whose header text matches "io" or "job" first; else first.
    for col in signals.identity_col_candidates:
        for hit in signals.header_vocab_hits.get(col, []):
            h = hit.lower()
            if "io" in h or "job" in h or "buyer po" in h:
                return col
    return signals.identity_col_candidates[0]


@component
class SheetRowPlanner:
    """Haystack component — emits a SheetPlan for one sheet."""

    @component.output_types(plan=SheetPlan)
    def run(self, workbook_ctx: Any, sheet: str) -> dict:
        signals = survey_sheet(workbook_ctx, sheet)
        pli_mode = _decide_pli_mode(signals)
        identity_column = (
            _pick_identity_column(signals) if pli_mode is not PliMode.SHEET_IS_PLI else None
        )

        stage_bands = detect_stage_bands(workbook_ctx, sheet, signals)
        kv_anchors = detect_kv_anchors(workbook_ctx, sheet, signals)

        rows: list[RowSpec] = []
        blocks: list[PliBlock] = []
        if pli_mode is PliMode.SHEET_IS_PLI:
            rows = []
        else:
            rows = classify_rows(workbook_ctx, sheet, signals,
                                identity_column=identity_column)
            header_rows = [r.idx for r in rows if r.role is RowRole.HEADER]
        header_rows = [r.idx for r in rows if r.role is RowRole.HEADER] if rows else []

        if pli_mode is PliMode.SECTION_PER_PLI:
            blocks = segment_blocks(rows, kv_anchors, signals.blank_run_gaps, stage_bands)
            # Bands attached to blocks; clear sheet-level bands.
            stage_bands_sheet: list[StageBandSpec] = []
            stage_scope = StageScope.PLI_LOCAL
        else:
            stage_bands_sheet = stage_bands
            stage_scope = StageScope.SHEET_LEVEL

        confidence = 0.9 if pli_mode is not PliMode.SHEET_IS_PLI else 0.85
        if pli_mode is PliMode.SHEET_IS_PLI and len(kv_anchors) >= 3:
            confidence = 0.92

        plan = SheetPlan(
            sheet=sheet,
            pli_mode=pli_mode,
            identity_column=identity_column,
            header_rows=header_rows,
            rows=rows,
            pli_blocks=blocks,
            kv_anchors=kv_anchors if pli_mode != PliMode.SECTION_PER_PLI else [],
            stage_bands=stage_bands_sheet,
            stage_scope=stage_scope,
            confidence=confidence,
        )
        return {"plan": plan}
```

- [ ] **Step 4: Run tests, expect PASS**

```
.venv/Scripts/python.exe -m pytest tests/unit/planner/test_plan.py -q
```
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/services/planner/plan.py tests/unit/planner/test_plan.py
git commit -m "feat(planner): SheetRowPlanner — emit SheetPlan per sheet"
```

---

## Phase 3 — Plan validators (T1 + T2)

### Task 13: `plan_invariants` — Tier 1 structural validators

**Files:**
- Create: `app/services/validation/plan_invariants.py`
- Test: `tests/unit/validation/test_plan_invariants.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/validation/test_plan_invariants.py
from app.models.artifacts import SheetPlan, RowSpec, PliBlock, KVAnchor, StageBandSpec
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.services.validation.plan_invariants import validate_invariants


def _plan(rows=None, **kw):
    return SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI, identity_column="B",
        header_rows=[1], rows=rows or [], stage_scope=StageScope.SHEET_LEVEL,
        confidence=1.0, **kw,
    )


def test_reference_integrity_pass():
    rows = [
        RowSpec(idx=2, role=RowRole.ANCHOR, group_id=0),
        RowSpec(idx=3, role=RowRole.CHILD, anchor_idx=2, group_id=0),
    ]
    findings = validate_invariants(_plan(rows=rows))
    assert all(f.severity != "error" for f in findings)


def test_reference_integrity_fail_dangling_anchor_idx():
    rows = [
        RowSpec(idx=3, role=RowRole.CHILD, anchor_idx=99),  # 99 doesn't exist
    ]
    findings = validate_invariants(_plan(rows=rows))
    assert any(f.check == "reference_integrity" and f.severity == "error"
               for f in findings)


def test_row_uniqueness_fail():
    rows = [
        RowSpec(idx=2, role=RowRole.ANCHOR),
        RowSpec(idx=2, role=RowRole.CHILD, anchor_idx=2),
    ]
    findings = validate_invariants(_plan(rows=rows))
    assert any(f.check == "row_uniqueness" for f in findings)


def test_pli_block_non_overlap_fail():
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.SECTION_PER_PLI,
        pli_blocks=[PliBlock(id=0, bbox=(3, 10)),
                    PliBlock(id=1, bbox=(8, 15))],  # overlap
        stage_scope=StageScope.PLI_LOCAL, confidence=1.0,
    )
    findings = validate_invariants(plan)
    assert any(f.check == "pli_block_non_overlap" for f in findings)
```

- [ ] **Step 2: Run tests, expect FAIL**

- [ ] **Step 3: Implement**

```python
# app/services/validation/plan_invariants.py
"""Tier 1 plan validators — structural invariants of a SheetPlan as a graph.

Errors here mean the plan is corrupt; the orchestrator should re-plan with
hints, not call PlanReviewer.
"""
from __future__ import annotations
from app.models.artifacts import SheetPlan, ValidationFinding
from app.enums.row_role import RowRole
from app.enums.validation_severity import ValidationSeverity


def _e(check: str, msg: str) -> ValidationFinding:
    return ValidationFinding(check=check, severity=ValidationSeverity.ERROR, message=msg)


def _w(check: str, msg: str) -> ValidationFinding:
    return ValidationFinding(check=check, severity=ValidationSeverity.WARN, message=msg)


def validate_invariants(plan: SheetPlan) -> list[ValidationFinding]:
    out: list[ValidationFinding] = []

    # ReferenceIntegrity
    valid_idxs = {r.idx for r in plan.rows}
    anchors = {r.idx for r in plan.rows if r.role is RowRole.ANCHOR}
    for r in plan.rows:
        if r.role is RowRole.ANCHOR and r.anchor_idx is not None:
            out.append(_e("reference_integrity",
                          f"ANCHOR row {r.idx} has non-null anchor_idx={r.anchor_idx}"))
        if r.role is RowRole.CHILD:
            if r.anchor_idx is None:
                out.append(_e("reference_integrity",
                              f"CHILD row {r.idx} has no anchor_idx"))
            elif r.anchor_idx not in anchors:
                out.append(_e("reference_integrity",
                              f"CHILD row {r.idx} anchor_idx={r.anchor_idx} not in ANCHOR rows"))

    # RowUniqueness
    seen: set[int] = set()
    for r in plan.rows:
        if r.idx in seen:
            out.append(_e("row_uniqueness", f"row idx {r.idx} appears more than once"))
        seen.add(r.idx)

    # HeaderContiguity
    if plan.header_rows:
        sorted_h = sorted(plan.header_rows)
        if sorted_h != list(range(sorted_h[0], sorted_h[-1] + 1)):
            out.append(_w("header_contiguity", "header rows are not contiguous"))
        if plan.rows:
            max_h = max(plan.header_rows)
            for r in plan.rows:
                if r.role in (RowRole.ANCHOR, RowRole.CHILD) and r.idx < max_h:
                    out.append(_w("header_contiguity",
                                  f"data row {r.idx} precedes max header row {max_h}"))
                    break

    # PliBlockNonOverlap
    blocks = sorted(plan.pli_blocks, key=lambda b: b.bbox[0])
    for i in range(len(blocks) - 1):
        if blocks[i].bbox[1] >= blocks[i + 1].bbox[0]:
            out.append(_e("pli_block_non_overlap",
                          f"blocks {blocks[i].id} {blocks[i].bbox} and "
                          f"{blocks[i+1].id} {blocks[i+1].bbox} overlap"))

    # SubRowConsistency
    by_group: dict[int, list] = {}
    for r in plan.rows:
        if r.group_id is not None:
            by_group.setdefault(r.group_id, []).append(r)
    for gid, members in by_group.items():
        sub_set = {bool(m.sub_row_role) for m in members}
        if len(sub_set) > 1:
            out.append(_w("sub_row_consistency",
                          f"group {gid} mixes sub_row_role set + unset"))

    return out
```

You will need to make sure `ValidationFinding` and `ValidationSeverity` already exist in this codebase — they do (`app/models/artifacts.py` and `app/enums/validation_severity.py`).

- [ ] **Step 4: Run tests, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add app/services/validation/plan_invariants.py tests/unit/validation/test_plan_invariants.py
git commit -m "feat(validation): plan_invariants — Tier 1 structural checks"
```

---

### Task 14: `plan_statistics` — Tier 2 statistical sanity validators

**Files:**
- Create: `app/services/validation/plan_statistics.py`
- Test: `tests/unit/validation/test_plan_statistics.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/validation/test_plan_statistics.py
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.models.artifacts import SheetPlan, RowSpec
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.services.validation.plan_statistics import validate_statistics


def _ctx(tmp_path, cells):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    for addr, val in cells.items():
        ws[addr] = val
    p = tmp_path / "x.xlsx"; wb.save(p)
    return register_workbook(p)


def test_sequence_match_pass(tmp_path):
    ctx = _ctx(tmp_path, {
        "A1": "S NO", "B1": "IO NO",
        "A2": 1, "B2": 1063,
        "A3": 2, "B3": 1064,
    })
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI, identity_column="B",
        header_rows=[1],
        rows=[RowSpec(idx=2, role=RowRole.ANCHOR, group_id=0),
              RowSpec(idx=3, role=RowRole.ANCHOR, group_id=1)],
        stage_scope=StageScope.SHEET_LEVEL, confidence=1.0,
    )
    findings = validate_statistics(ctx, plan)
    assert all(f.check != "sequence_match" or f.severity != "error"
               for f in findings)


def test_pli_count_sanity_warn(tmp_path):
    """Sheet has many data rows but plan emits zero ANCHORs."""
    ctx = _ctx(tmp_path, {
        "A1": "IO NO", **{f"A{i}": str(1000 + i) for i in range(2, 20)},
    })
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI, identity_column="A",
        rows=[], stage_scope=StageScope.SHEET_LEVEL, confidence=1.0,
    )
    findings = validate_statistics(ctx, plan)
    assert any(f.check == "pli_count_sanity" for f in findings)
```

- [ ] **Step 2: Run tests, expect FAIL**

- [ ] **Step 3: Implement**

```python
# app/services/validation/plan_statistics.py
"""Tier 2 plan validators — statistical sanity of a SheetPlan against the sheet.

Warnings here cause PlanReviewer to fire; errors trigger re-plan with hints.
"""
from __future__ import annotations
from datetime import date, datetime
from openpyxl.utils import column_index_from_string
from app.models.workbook import WorkbookCtx
from app.models.artifacts import SheetPlan, ValidationFinding
from app.enums.row_role import RowRole
from app.enums.validation_severity import ValidationSeverity


def _w(check: str, msg: str) -> ValidationFinding:
    return ValidationFinding(check=check, severity=ValidationSeverity.WARN, message=msg)


def validate_statistics(ctx: WorkbookCtx, plan: SheetPlan) -> list[ValidationFinding]:
    out: list[ValidationFinding] = []
    ws = ctx.wb[plan.sheet]
    anchors = [r for r in plan.rows if r.role is RowRole.ANCHOR]

    # SequenceMatch — when an S.NO-like column exists.
    sno_col = None
    for c in range(1, (ws.max_column or 0) + 1):
        for h_row in plan.header_rows:
            v = ws.cell(row=h_row, column=c).value
            if isinstance(v, str) and v.strip().lower() in ("s no", "s.no", "sno", "s. no", "sl no"):
                sno_col = c
                break
        if sno_col:
            break
    if sno_col is not None and anchors:
        sno_vals = [ws.cell(row=a.idx, column=sno_col).value for a in anchors]
        sno_ints = [int(v) for v in sno_vals if isinstance(v, (int, float))]
        if sno_ints:
            expected = max(sno_ints)
            if expected != len(anchors):
                out.append(_w("sequence_match",
                              f"S.NO max={expected} vs ANCHOR count={len(anchors)}"))

    # PliCountSanity — non-trivial sheet with no PLIs.
    max_row = ws.max_row or 0
    if max_row >= 10 and len(anchors) == 0 and len(plan.pli_blocks) == 0 and len(plan.kv_anchors) == 0:
        out.append(_w("pli_count_sanity",
                      f"sheet has {max_row} rows but plan emits 0 PLIs"))

    # IdentityColumnCoverage — for ROW_PER_PLI mode.
    if plan.identity_column and plan.rows:
        id_col = column_index_from_string(plan.identity_column)
        data_rows = [r for r in plan.rows
                     if r.role in (RowRole.ANCHOR, RowRole.CHILD)]
        if data_rows:
            populated = sum(
                1 for r in data_rows
                if ws.cell(row=r.idx, column=id_col).value is not None
                or r.anchor_idx is not None
            )
            ratio = populated / len(data_rows)
            if ratio < 0.8:
                out.append(_w("identity_column_coverage",
                              f"identity coverage {ratio:.2f} < 0.80"))

    # DateBandDensity — stage bands should be ≥50% date-typed.
    for band in plan.stage_bands:
        sub_rows = list(band.sub_rows.values())
        if not sub_rows:
            continue
        total = 0; dates = 0
        for col_letter in band.stage_cols.values():
            c_idx = column_index_from_string(col_letter)
            for r in sub_rows:
                v = ws.cell(row=r, column=c_idx).value
                if v is None:
                    continue
                total += 1
                if isinstance(v, (date, datetime)):
                    dates += 1
        if total >= 2 and dates / total < 0.5:
            out.append(_w("date_band_density",
                          f"stage band '{band.name}' is only {dates}/{total} date-typed"))

    return out
```

- [ ] **Step 4: Run tests, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add app/services/validation/plan_statistics.py tests/unit/validation/test_plan_statistics.py
git commit -m "feat(validation): plan_statistics — Tier 2 sanity checks"
```

---

## Phase 4 — New LLM agents (LayoutHinter, PlanReviewer, FieldNamer)

### Task 15: `LayoutHinter` agent — disambiguation when planner is stuck

**Files:**
- Create: `app/prompts/workflow/layout_hinter.md`
- Create: `app/services/agents/layout_hinter.py`
- Test: `tests/unit/agents/test_layout_hinter.py`

- [ ] **Step 1: Write the prompt**

```markdown
# app/prompts/workflow/layout_hinter.md
You are LayoutHinter. The deterministic SheetRowPlanner could not decide one
or more of the following:
- which column is the identity column (when there are 2+ candidates)
- which pli_mode is correct for this sheet

You are given the sheet's signals + a top-left peek. Pick the best
identity_column and/or pli_mode. Return JSON matching the LayoutHints schema.

Rules:
- Prefer columns whose header text contains "IO", "JOB", "BUYER PO".
- Prefer pli_mode=SHEET_IS_PLI only when the sheet has no row-tabular data.
- Keep notes short; one sentence per signal you used.
```

- [ ] **Step 2: Write the agent + a smoke test**

```python
# tests/unit/agents/test_layout_hinter.py
from app.services.agents.layout_hinter import SPEC


def test_layout_hinter_spec_loaded():
    assert SPEC.name == "layout_hinter"
    assert SPEC.output_schema.__name__ == "LayoutHints"
```

- [ ] **Step 3: Run, expect FAIL** (`ModuleNotFoundError`).

- [ ] **Step 4: Implement**

```python
# app/services/agents/layout_hinter.py
"""LayoutHinter — LLM disambiguator for identity_column / pli_mode."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from haystack import component
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.models.artifacts import LayoutHints, SheetSignals
from app.services.llm_provider import LLMProvider
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.core.prompt_loader import load_prompt

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: Any, inputs: dict) -> str:
    sig: SheetSignals = inputs["signals"]
    sheet = inputs["sheet"]
    peek = TOOL_REGISTRY.get("peek_sheet")
    grid = peek(ctx, sheet, rows=10, cols=15)

    lines = [f"# Sheet: {sheet}", "## Signals:", str(sig.model_dump()), "",
             "## Top-left peek (rows 1..10, cols 1..15):"]
    for c in grid.cells:
        lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
    return "\n".join(lines)


SPEC = AgentSpec(
    name="layout_hinter",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "layout_hinter.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=LayoutHints,
    build_user_input=_build_user_input,
)


@component
class LayoutHinter:
    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(hints=LayoutHints)
    def run(self, workbook_ctx: Any, sheet: str, signals: SheetSignals) -> dict:
        result = self.runner.run(workbook_ctx, {"sheet": sheet, "signals": signals})
        if isinstance(result, AgentRunFailure):
            return {"hints": LayoutHints()}
        return {"hints": result}
```

- [ ] **Step 5: Run smoke test, expect PASS**

- [ ] **Step 6: Commit**

```bash
git add app/prompts/workflow/layout_hinter.md app/services/agents/layout_hinter.py tests/unit/agents/test_layout_hinter.py
git commit -m "feat(agents): LayoutHinter — disambiguation agent"
```

---

### Task 16: `PlanReviewer` agent — LLM judge of the plan

**Files:**
- Create: `app/prompts/workflow/plan_reviewer.md`
- Create: `app/services/agents/plan_reviewer.py`
- Test: `tests/unit/agents/test_plan_reviewer.py`

- [ ] **Step 1: Write the prompt**

```markdown
# app/prompts/workflow/plan_reviewer.md
You are PlanReviewer. You are given a draft SheetPlan + Tier 1/2 validator
findings + a peek at the sheet. Your job is to judge whether the plan looks
correct.

Output JSON matching PlanVerdict:
- verdict: "looks_correct" or "needs_fix"
- row_corrections: list of {row, current_role, suggested_role, anchor_idx?, reason}
- identity_column_suggestion: column letter or null
- warnings: short strings flagging stage-band / KV anchor concerns
- confidence: 0..1

Rules:
- If you disagree with a strong deterministic signal (e.g., sum-of-children
  matches a TOTAL row), say so in warnings but DO NOT override — the det
  classification will win.
- Be specific about row numbers. Do not hallucinate row indices outside the
  plan you are shown.
- Limit row_corrections to ≤5 items.
```

- [ ] **Step 2: Smoke test**

```python
# tests/unit/agents/test_plan_reviewer.py
from app.services.agents.plan_reviewer import SPEC


def test_plan_reviewer_spec_loaded():
    assert SPEC.name == "plan_reviewer"
    assert SPEC.output_schema.__name__ == "PlanVerdict"
```

- [ ] **Step 3: Run, expect FAIL**

- [ ] **Step 4: Implement**

```python
# app/services/agents/plan_reviewer.py
"""PlanReviewer — LLM judge of SheetPlan correctness.

Fires only when Tier 1/2 validators warned, plan confidence is low, or mode
is one of the rarer modes (SECTION_PER_PLI / SHEET_IS_PLI).
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from haystack import component
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.models.artifacts import PlanVerdict, SheetPlan, ValidationFinding
from app.services.llm_provider import LLMProvider
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.core.prompt_loader import load_prompt

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: Any, inputs: dict) -> str:
    plan: SheetPlan = inputs["plan"]
    findings: list[ValidationFinding] = inputs.get("findings", [])
    sheet = plan.sheet
    peek = TOOL_REGISTRY.get("peek_sheet")
    grid = peek(ctx, sheet, rows=20, cols=15)

    lines = [
        f"# Sheet: {sheet}",
        "## Plan summary:",
        str(plan.model_dump(exclude_none=True)),
        "",
        "## Tier 1/2 warnings:",
    ]
    for f in findings:
        lines.append(f"  - [{f.severity}] {f.check}: {f.message}")
    lines.append("")
    lines.append("## Sheet peek (rows 1..20, cols 1..15):")
    for c in grid.cells:
        lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
    return "\n".join(lines)


SPEC = AgentSpec(
    name="plan_reviewer",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "plan_reviewer.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=PlanVerdict,
    build_user_input=_build_user_input,
)


@component
class PlanReviewer:
    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(verdict=PlanVerdict)
    def run(self, workbook_ctx: Any, plan: SheetPlan,
            findings: list[ValidationFinding] | None = None) -> dict:
        result = self.runner.run(workbook_ctx,
                                 {"plan": plan, "findings": findings or []})
        if isinstance(result, AgentRunFailure):
            return {"verdict": PlanVerdict(verdict="looks_correct", confidence=0.0)}
        return {"verdict": result}
```

- [ ] **Step 5: Run, expect PASS**

- [ ] **Step 6: Commit**

```bash
git add app/prompts/workflow/plan_reviewer.md app/services/agents/plan_reviewer.py tests/unit/agents/test_plan_reviewer.py
git commit -m "feat(agents): PlanReviewer — LLM judge of SheetPlan"
```

---

### Task 17: `FieldNamer` agent — labels → canonical fields

**Files:**
- Create: `app/prompts/workflow/field_namer.md`
- Create: `app/services/agents/field_namer.py`
- Test: `tests/unit/agents/test_field_namer.py`

- [ ] **Step 1: Write the prompt**

```markdown
# app/prompts/workflow/field_namer.md
You are FieldNamer. Map supplier labels and stage column headers to canonical
names.

Canonical field names:
  io_number, style_code, style_name, color_code, color_name, fabric_code,
  delivery_date, quantity, order_quantity, plan_quantity, order_receipt_date,
  pps_completion, sample_completion, ex_factory_date

Canonical stage names (drop into Stage.name):
  fabric, lab_dip_send, lab_dip_approval, fit_send, fit_approval,
  art_work_send, art_work_approval, in_house_fabric_send,
  in_house_fabric_approval, pre_production_send, pre_production_approval,
  first_pattern, garment_pattern, planned_completion_date,
  size_set, lot_card, cutting, feeding, sewing, final_inspection

Output JSON matching CanonicalNameMap:
- field_labels: {original_label: canonical_field_name | "ignore"}
- stage_names: {original_stage_header: canonical_stage_name | "ignore"}

Use "ignore" for labels that aren't worth extracting.
```

- [ ] **Step 2: Smoke test**

```python
# tests/unit/agents/test_field_namer.py
from app.services.agents.field_namer import SPEC


def test_field_namer_spec_loaded():
    assert SPEC.name == "field_namer"
    assert SPEC.output_schema.__name__ == "CanonicalNameMap"
```

- [ ] **Step 3: Run, expect FAIL**

- [ ] **Step 4: Implement**

```python
# app/services/agents/field_namer.py
"""FieldNamer — map detected labels and stage column headers to canonical names."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from haystack import component
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.models.artifacts import CanonicalNameMap, SheetPlan
from app.services.llm_provider import LLMProvider
from app.core.prompt_loader import load_prompt

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: Any, inputs: dict) -> str:
    plan: SheetPlan = inputs["plan"]
    labels = {kv.field for kv in plan.kv_anchors}
    for blk in plan.pli_blocks:
        for kv in blk.identity:
            labels.add(kv.field)
    stage_headers: set[str] = set()
    for band in plan.stage_bands:
        stage_headers.update(band.stage_cols.keys())
    for blk in plan.pli_blocks:
        for band in blk.stage_bands:
            stage_headers.update(band.stage_cols.keys())

    lines = [f"# Sheet: {plan.sheet}",
             "## Detected labels:"]
    for l in sorted(labels):
        lines.append(f"  - {l!r}")
    lines.append("")
    lines.append("## Detected stage column headers:")
    for h in sorted(stage_headers):
        lines.append(f"  - {h!r}")
    return "\n".join(lines)


SPEC = AgentSpec(
    name="field_namer",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "field_namer.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=CanonicalNameMap,
    build_user_input=_build_user_input,
)


@component
class FieldNamer:
    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(name_map=CanonicalNameMap)
    def run(self, workbook_ctx: Any, plan: SheetPlan) -> dict:
        result = self.runner.run(workbook_ctx, {"plan": plan})
        if isinstance(result, AgentRunFailure):
            return {"name_map": CanonicalNameMap()}
        return {"name_map": result}
```

- [ ] **Step 5: Run, expect PASS**

- [ ] **Step 6: Commit**

```bash
git add app/prompts/workflow/field_namer.md app/services/agents/field_namer.py tests/unit/agents/test_field_namer.py
git commit -m "feat(agents): FieldNamer — labels → canonical names"
```

---

## Phase 5 — `apply_plan` (100% deterministic resolver)

### Task 18: `apply_plan` — ROW_PER_PLI mode (single-row PLIs)

**Files:**
- Create: `app/services/applier/apply_plan.py`
- Test: `tests/unit/applier/test_apply_plan_row_per_pli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/applier/test_apply_plan_row_per_pli.py
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.models.artifacts import SheetPlan, RowSpec, CanonicalNameMap
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.services.applier.apply_plan import apply_plan


def test_row_per_pli_two_anchors_with_children(tmp_path):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    ws["A1"] = "IO NO"; ws["B1"] = "COLOR"; ws["C1"] = "QTY"
    ws["A2"] = "1063"; ws["B2"] = "MAGENTA"; ws["C2"] = 2356
    ws["B3"] = "NAVY"; ws["C3"] = 2356
    ws["A4"] = "1064"; ws["B4"] = "PINE"; ws["C4"] = 2050
    ws.merge_cells("A2:A3")
    p = tmp_path / "x.xlsx"; wb.save(p)
    ctx = register_workbook(p)

    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI, identity_column="A",
        header_rows=[1],
        rows=[
            RowSpec(idx=2, role=RowRole.ANCHOR, group_id=0),
            RowSpec(idx=3, role=RowRole.CHILD, anchor_idx=2, group_id=0),
            RowSpec(idx=4, role=RowRole.ANCHOR, group_id=1),
        ],
        stage_scope=StageScope.SHEET_LEVEL, confidence=1.0,
    )
    name_map = CanonicalNameMap(
        field_labels={"IO NO": "io_number", "COLOR": "color_code", "QTY": "quantity"},
    )
    plis = apply_plan(ctx, plan, name_map)
    assert len(plis) == 3
    assert plis[0].io_number == "1063"
    assert plis[0].color_code == "MAGENTA"
    assert plis[1].io_number == "1063"  # propagated via merge anchor
    assert plis[1].color_code == "NAVY"
    assert plis[2].io_number == "1064"
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement initial structure**

```python
# app/services/applier/apply_plan.py
"""Pure deterministic resolver: (SheetPlan, CanonicalNameMap) → list[PLI].

100% LLM-free. Dispatches on pli_mode. Reads cells via WorkbookCtx +
get_merged_regions; never calls any LLM agent or external service.
"""
from __future__ import annotations
from datetime import date, datetime
from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.utils.cell import coordinate_from_string
from app.models.workbook import WorkbookCtx
from app.models.extraction import PLI, Stage
from app.models.artifacts import (
    SheetPlan, RowSpec, KVAnchor, StageBandSpec, PliBlock, CanonicalNameMap,
)
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole


_DATA_ROLES = {RowRole.ANCHOR, RowRole.CHILD}
_STRING_FIELDS = {"io_number", "style_code", "style_name",
                  "color_code", "color_name", "fabric_code"}


def _coerce(field: str, val):
    if field in _STRING_FIELDS and val is not None:
        return str(val)
    return val


def _read_with_merge(ws, row: int, col_idx: int) -> tuple[object, str]:
    """Read a cell, falling back to the merge anchor if blank."""
    direct = ws.cell(row=row, column=col_idx).value
    if direct is not None:
        return direct, f"{get_column_letter(col_idx)}{row}"
    for mr in ws.merged_cells.ranges:
        if mr.min_row <= row <= mr.max_row and mr.min_col <= col_idx <= mr.max_col:
            anc_val = ws.cell(row=mr.min_row, column=mr.min_col).value
            return anc_val, f"{get_column_letter(mr.min_col)}{mr.min_row}"
    return None, f"{get_column_letter(col_idx)}{row}"


def _read_kv_into(values: dict, source_cells: dict, ws, kv: KVAnchor, name_map: CanonicalNameMap):
    canonical = name_map.field_labels.get(kv.field, kv.field)
    if canonical == "ignore":
        return
    col_letter, row = coordinate_from_string(kv.value_cell)
    col = column_index_from_string(col_letter)
    val = ws.cell(row=row, column=col).value
    if val is None:
        return
    values[canonical] = _coerce(canonical, val)
    source_cells[canonical] = kv.value_cell


def _apply_row_per_pli(ctx: WorkbookCtx, plan: SheetPlan,
                      name_map: CanonicalNameMap) -> list[PLI]:
    ws = ctx.wb[plan.sheet]
    plis: list[PLI] = []
    rows_by_group: dict[int, list[RowSpec]] = {}
    for r in plan.rows:
        if r.role not in _DATA_ROLES:
            continue
        if r.group_id is not None:
            rows_by_group.setdefault(r.group_id, []).append(r)
        else:
            rows_by_group.setdefault(r.idx, []).append(r)

    # Build header row → {col_idx: original_label} map for translation.
    header_label_by_col: dict[int, str] = {}
    for h_row in plan.header_rows:
        for c in range(1, (ws.max_column or 0) + 1):
            v = ws.cell(row=h_row, column=c).value
            if isinstance(v, str) and v.strip():
                header_label_by_col.setdefault(c, v.strip())

    for gid, group_rows in rows_by_group.items():
        is_multi_row_pli = all(r.sub_row_role is not None for r in group_rows)

        if is_multi_row_pli:
            plis.append(_emit_multi_row_pli(ws, plan, group_rows,
                                            header_label_by_col, name_map))
            continue

        for r in group_rows:
            plis.append(_emit_single_row_pli(ws, plan, r,
                                             header_label_by_col, name_map))
    return plis


def _emit_single_row_pli(ws, plan: SheetPlan, row: RowSpec,
                         header_label_by_col: dict[int, str],
                         name_map: CanonicalNameMap) -> PLI:
    values: dict = {"metadata": {}}
    source_cells: dict[str, str] = {}

    for col_idx, label in header_label_by_col.items():
        canonical = name_map.field_labels.get(label, label)
        if canonical == "ignore":
            continue
        val, addr = _read_with_merge(ws, row.idx, col_idx)
        if val is None:
            continue
        if canonical in PLI.model_fields:
            values[canonical] = _coerce(canonical, val)
            source_cells[canonical] = addr
        else:
            values["metadata"][canonical] = val
            source_cells[canonical] = addr

    # Sheet-level KV anchors apply to every PLI on the sheet.
    for kv in plan.kv_anchors:
        _read_kv_into(values, source_cells, ws, kv, name_map)

    values["source"] = {"sheet": plan.sheet, "rows": [row.idx], "cells": source_cells}
    values["stages"] = _read_stages(ws, plan.stage_bands, row.idx, name_map, source_cells)
    return PLI(**values)


def _emit_multi_row_pli(ws, plan, group_rows, header_label_by_col, name_map) -> PLI:
    anchor_row = next(r for r in group_rows if r.role is RowRole.ANCHOR)
    pli = _emit_single_row_pli(ws, plan, anchor_row, header_label_by_col, name_map)
    # Fold child rows' sub_row_role values into stages metadata under each stage.
    for r in group_rows:
        if r is anchor_row:
            continue
        # The actual fold semantics are stage-band-dependent; for now we record
        # child row presence in metadata and let downstream handle.
        pli.metadata.setdefault("multi_row_sub_rows", []).append({
            "row": r.idx, "sub_row_role": r.sub_row_role.value if r.sub_row_role else None,
        })
    return pli


def _read_stages(ws, bands: list[StageBandSpec], pli_row: int,
                 name_map: CanonicalNameMap, parent_source: dict) -> list[Stage]:
    stages: list[Stage] = []
    for band in bands:
        for stage_name, col_letter in band.stage_cols.items():
            canonical_stage = name_map.stage_names.get(stage_name, stage_name)
            if canonical_stage == "ignore":
                continue
            c_idx = column_index_from_string(col_letter)
            if band.layout_mode == "wide_sub_columns":
                val, addr = _read_with_merge(ws, pli_row, c_idx)
                if val is None:
                    continue
                stages.append(Stage(
                    name=canonical_stage,
                    planned_date=val if isinstance(val, (date, datetime)) else None,
                    section=band.name,
                    source={"sheet": ws.title, "rows": [pli_row],
                           "cells": {"planned_date": addr}},
                ))
            else:  # tall_sub_rows
                plan_row = band.sub_rows.get("plan")
                if plan_row is None:
                    continue
                pv, pa = _read_with_merge(ws, plan_row, c_idx)
                if pv is None:
                    continue
                metadata: dict = {}
                source_cells = {"planned_date": pa}
                for role, row_idx in band.sub_rows.items():
                    if role == "plan":
                        continue
                    av = ws.cell(row=row_idx, column=c_idx).value
                    if av is not None:
                        metadata[role] = av
                        source_cells[role] = f"{col_letter}{row_idx}"
                stages.append(Stage(
                    name=canonical_stage,
                    planned_date=pv if isinstance(pv, (date, datetime)) else None,
                    section=band.name, metadata=metadata,
                    source={"sheet": ws.title, "rows": sorted(band.sub_rows.values()),
                           "cells": source_cells},
                ))
    return stages


def _apply_section_per_pli(ctx: WorkbookCtx, plan: SheetPlan,
                          name_map: CanonicalNameMap) -> list[PLI]:
    ws = ctx.wb[plan.sheet]
    plis: list[PLI] = []
    for blk in plan.pli_blocks:
        values: dict = {"metadata": {}}
        source_cells: dict[str, str] = {}
        for kv in blk.identity:
            _read_kv_into(values, source_cells, ws, kv, name_map)
        values["source"] = {"sheet": plan.sheet,
                            "rows": list(range(blk.bbox[0], blk.bbox[1] + 1)),
                            "cells": source_cells}
        values["stages"] = []
        for band in blk.stage_bands:
            # Bands inside a block read at the band's plan_row, not a PLI row.
            plan_row = band.sub_rows.get("plan")
            if plan_row is not None:
                values["stages"].extend(
                    _read_stages(ws, [band], plan_row, name_map, source_cells)
                )
        plis.append(PLI(**values))
    return plis


def _apply_sheet_is_pli(ctx: WorkbookCtx, plan: SheetPlan,
                       name_map: CanonicalNameMap) -> list[PLI]:
    ws = ctx.wb[plan.sheet]
    values: dict = {"metadata": {}}
    source_cells: dict[str, str] = {}
    for kv in plan.kv_anchors:
        _read_kv_into(values, source_cells, ws, kv, name_map)
    values["source"] = {"sheet": plan.sheet, "rows": [], "cells": source_cells}
    values["stages"] = []
    for band in plan.stage_bands:
        plan_row = band.sub_rows.get("plan")
        if plan_row is not None:
            values["stages"].extend(
                _read_stages(ws, [band], plan_row, name_map, source_cells)
            )
    return [PLI(**values)]


def apply_plan(ctx: WorkbookCtx, plan: SheetPlan,
               name_map: CanonicalNameMap) -> list[PLI]:
    """Dispatch on pli_mode. Pure function — no LLM calls."""
    if plan.pli_mode is PliMode.ROW_PER_PLI:
        return _apply_row_per_pli(ctx, plan, name_map)
    if plan.pli_mode is PliMode.SECTION_PER_PLI:
        return _apply_section_per_pli(ctx, plan, name_map)
    if plan.pli_mode is PliMode.SHEET_IS_PLI:
        return _apply_sheet_is_pli(ctx, plan, name_map)
    raise ValueError(f"unknown pli_mode: {plan.pli_mode}")
```

- [ ] **Step 4: Run, expect PASS**

```
.venv/Scripts/python.exe -m pytest tests/unit/applier/test_apply_plan_row_per_pli.py -q
```

- [ ] **Step 5: Commit**

```bash
git add app/services/applier/apply_plan.py tests/unit/applier/test_apply_plan_row_per_pli.py
git commit -m "feat(applier): apply_plan ROW_PER_PLI mode (single-row PLIs + merge propagation)"
```

---

### Task 19: `apply_plan` — SHEET_IS_PLI mode

**Files:**
- Test: `tests/unit/applier/test_apply_plan_sheet_is_pli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/applier/test_apply_plan_sheet_is_pli.py
from datetime import datetime
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.models.artifacts import SheetPlan, KVAnchor, StageBandSpec, CanonicalNameMap
from app.enums.pli_mode import PliMode
from app.enums.stage_scope import StageScope
from app.services.applier.apply_plan import apply_plan


def test_sheet_is_pli_one_pli_per_sheet(tmp_path):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "63315"
    ws["A4"] = "Job No"; ws["B4"] = 63315
    ws["A5"] = "Quantity"; ws["B5"] = 254886
    ws["A8"] = "Pre-Prod TNA"
    ws["C8"] = "L/D send"; ws["D8"] = "Fit send"
    ws["C9"] = datetime(2026, 3, 1)
    ws["D9"] = datetime(2026, 3, 5)
    p = tmp_path / "x.xlsx"; wb.save(p)
    ctx = register_workbook(p)

    plan = SheetPlan(
        sheet="63315", pli_mode=PliMode.SHEET_IS_PLI,
        kv_anchors=[
            KVAnchor(label_cell="A4", value_cell="B4", field="Job No"),
            KVAnchor(label_cell="A5", value_cell="B5", field="Quantity"),
        ],
        stage_bands=[StageBandSpec(
            name="Pre-Prod TNA", name_cell="A8", sub_header_row=8,
            sub_rows={"plan": 9},
            stage_cols={"L/D send": "C", "Fit send": "D"},
            layout_mode="wide_sub_columns",
        )],
        stage_scope=StageScope.SHEET_LEVEL, confidence=1.0,
    )
    name_map = CanonicalNameMap(
        field_labels={"Job No": "io_number", "Quantity": "quantity"},
        stage_names={"L/D send": "lab_dip_send", "Fit send": "fit_send"},
    )
    plis = apply_plan(ctx, plan, name_map)
    assert len(plis) == 1
    assert plis[0].io_number == "63315"
    assert plis[0].quantity == 254886
    names = [s.name for s in plis[0].stages]
    assert "lab_dip_send" in names
    assert "fit_send" in names
```

- [ ] **Step 2: Run, expect PASS** (the SHEET_IS_PLI path is already implemented).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/applier/test_apply_plan_sheet_is_pli.py
git commit -m "test(applier): apply_plan SHEET_IS_PLI mode"
```

---

### Task 20: `apply_plan` — SECTION_PER_PLI mode

**Files:**
- Test: `tests/unit/applier/test_apply_plan_section_per_pli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/applier/test_apply_plan_section_per_pli.py
from datetime import datetime
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.models.artifacts import (
    SheetPlan, PliBlock, KVAnchor, StageBandSpec, CanonicalNameMap,
)
from app.enums.pli_mode import PliMode
from app.enums.stage_scope import StageScope
from app.services.applier.apply_plan import apply_plan


def test_section_per_pli_two_blocks(tmp_path):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    ws["A4"] = "IO"; ws["B4"] = 1063
    ws["C8"] = "Cut"; ws["D8"] = "Sew"
    ws["C9"] = datetime(2026, 3, 12); ws["D9"] = datetime(2026, 4, 3)
    ws["A14"] = "IO"; ws["B14"] = 1064
    ws["C18"] = "Cut"; ws["D18"] = "Sew"
    ws["C19"] = datetime(2026, 4, 16); ws["D19"] = datetime(2026, 4, 25)
    p = tmp_path / "x.xlsx"; wb.save(p)
    ctx = register_workbook(p)

    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.SECTION_PER_PLI,
        pli_blocks=[
            PliBlock(id=0, bbox=(4, 10),
                identity=[KVAnchor(label_cell="A4", value_cell="B4", field="IO")],
                stage_bands=[StageBandSpec(
                    name="ProdBand", name_cell="C8", sub_header_row=8,
                    sub_rows={"plan": 9},
                    stage_cols={"Cut": "C", "Sew": "D"},
                    layout_mode="wide_sub_columns")]),
            PliBlock(id=1, bbox=(14, 20),
                identity=[KVAnchor(label_cell="A14", value_cell="B14", field="IO")],
                stage_bands=[StageBandSpec(
                    name="ProdBand", name_cell="C18", sub_header_row=18,
                    sub_rows={"plan": 19},
                    stage_cols={"Cut": "C", "Sew": "D"},
                    layout_mode="wide_sub_columns")]),
        ],
        stage_scope=StageScope.PLI_LOCAL, confidence=1.0,
    )
    name_map = CanonicalNameMap(
        field_labels={"IO": "io_number"},
        stage_names={"Cut": "cutting", "Sew": "sewing"},
    )
    plis = apply_plan(ctx, plan, name_map)
    assert len(plis) == 2
    assert plis[0].io_number == "1063"
    assert plis[1].io_number == "1064"
    assert any(s.name == "cutting" for s in plis[0].stages)
```

- [ ] **Step 2: Run, expect PASS or fix bugs in `_apply_section_per_pli` until pass**

- [ ] **Step 3: Commit**

```bash
git add tests/unit/applier/test_apply_plan_section_per_pli.py
git commit -m "test(applier): apply_plan SECTION_PER_PLI mode"
```

---

### Task 21: Static-analysis guard — `apply_plan` is LLM-free

**Files:**
- Test: `tests/unit/applier/test_apply_plan_no_llm_imports.py`

- [ ] **Step 1: Write the test**

```python
# tests/unit/applier/test_apply_plan_no_llm_imports.py
"""Static guarantee that apply_plan does not import LLM-related modules."""
import ast
from pathlib import Path


_BANNED = ("app.services.agents", "app.services.llm_provider", "anthropic", "openai")


def test_apply_plan_no_llm_imports():
    path = Path("app/services/applier/apply_plan.py").resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
    for imp in imports:
        for banned in _BANNED:
            assert not imp.startswith(banned), (
                f"apply_plan.py imports {imp}, which is banned (LLM/agent)"
            )
```

- [ ] **Step 2: Run, expect PASS**

- [ ] **Step 3: Commit**

```bash
git add tests/unit/applier/test_apply_plan_no_llm_imports.py
git commit -m "test(applier): static guard — apply_plan has no LLM imports"
```

---

## Phase 6 — Orchestrator rewrite

### Task 22: Rewrite `app/services/extraction.py` to use SheetRowPlanner

**Files:**
- Modify: `app/services/extraction.py`
- Test: `tests/integration/test_extraction_pipeline.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_extraction_pipeline.py
"""End-to-end smoke test of the rewritten extraction pipeline with a fake LLM."""
from openpyxl import Workbook
from app.repositories.workbook_repo import clear_cache
from app.services.extraction import extract


class _FakeLLM:
    """Stub that satisfies LLMProvider Protocol — returns canned outputs."""
    def respond(self, messages, schema, tools=None):
        name = schema.__name__
        if name == "RelevantSheets":
            return {"relevant_sheets": ["S"]}
        if name == "CanonicalNameMap":
            return {"field_labels": {"IO NO": "io_number", "COLOR": "color_code"},
                    "stage_names": {}}
        if name == "LayoutHints":
            return {}
        if name == "PlanVerdict":
            return {"verdict": "looks_correct"}
        raise NotImplementedError(name)


def test_extract_christian_berg_like(tmp_path):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    ws["A1"] = "IO NO"; ws["B1"] = "COLOR"
    ws["A2"] = "1063"; ws["B2"] = "MAGENTA"
    ws["B3"] = "NAVY"
    ws.merge_cells("A2:A3")
    p = tmp_path / "x.xlsx"; wb.save(p)

    result = extract(p, llm=_FakeLLM())
    assert len(result.plis) == 2
    assert result.plis[0].io_number == "1063"
    assert result.plis[1].io_number == "1063"
```

- [ ] **Step 2: Run, expect FAIL** (old extraction.py still wires up old agents).

- [ ] **Step 3: Implement — rewrite `app/services/extraction.py`**

Replace the file contents with:

```python
"""Top-level orchestration with the new SheetRowPlanner-based pipeline."""
from __future__ import annotations
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from app.repositories.workbook_repo import register_workbook
from app.models.extraction import ExtractionResult, PLI, Warning
from app.models.artifacts import (
    SheetPlan, CanonicalNameMap, LayoutHints, PlanVerdict, ValidationFindings,
)
from app.enums.pli_mode import PliMode
from app.enums.validation_severity import ValidationSeverity
from app.services.llm_provider import AnthropicProvider
from app.services.agents.sheet_classifier import SheetClassifier
from app.services.agents.layout_hinter import LayoutHinter
from app.services.agents.plan_reviewer import PlanReviewer
from app.services.agents.field_namer import FieldNamer
from app.services.planner.plan import SheetRowPlanner
from app.services.validation.plan_invariants import validate_invariants
from app.services.validation.plan_statistics import validate_statistics
from app.services.applier.apply_plan import apply_plan
from app.services.validation.source_cell_verifier import SourceCellVerifier
from app.services.validation.header_match_verifier import HeaderMatchVerifier
from app.services.validation.coverage_verifier import CoverageVerifier
from app.services.validation.field_dropout_verifier import FieldDropoutVerifier
from app.services.reconciler import reconcile
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.core.logs import get_logger
from app.core.telemetry import extraction_duration_seconds, extraction_pli_count
import app.repositories.workbook_tools.survey  # noqa: F401
import app.repositories.workbook_tools.bulk_read  # noqa: F401
import app.repositories.workbook_tools.targeted  # noqa: F401
import app.repositories.workbook_tools.structure  # noqa: F401
import app.repositories.workbook_tools.search  # noqa: F401

log = get_logger(__name__)

_CONFIDENCE_GATE = 0.85


def _plan_for_sheet(ctx, sheet: str, llm) -> tuple[SheetPlan, CanonicalNameMap, list[Warning]]:
    warnings: list[Warning] = []
    planner = SheetRowPlanner()
    plan: SheetPlan = planner.run(workbook_ctx=ctx, sheet=sheet)["plan"]

    findings_t1 = validate_invariants(plan)
    findings_t2 = validate_statistics(ctx, plan)
    findings = findings_t1 + findings_t2
    errors = [f for f in findings if f.severity == ValidationSeverity.ERROR]
    warns = [f for f in findings if f.severity == ValidationSeverity.WARN]

    needs_reviewer = (
        bool(warns)
        or plan.confidence < _CONFIDENCE_GATE
        or plan.pli_mode is not PliMode.ROW_PER_PLI
    )

    if errors:
        # Try one re-plan with LayoutHinter.
        hinter = LayoutHinter(llm=llm)
        hints: LayoutHints = hinter.run(
            workbook_ctx=ctx, sheet=sheet,
            signals=_signals_from_plan(ctx, plan),
        )["hints"]
        if hints.identity_column_suggestion:
            plan = SheetPlan(
                **{**plan.model_dump(),
                   "identity_column": hints.identity_column_suggestion},
            )
        # Re-validate after hint.
        findings_t1 = validate_invariants(plan)
        findings_t2 = validate_statistics(ctx, plan)
        for f in findings_t1 + findings_t2:
            warnings.append(Warning(message=f"{f.check}: {f.message}", severity="warning"))

    if needs_reviewer:
        reviewer = PlanReviewer(llm=llm)
        verdict: PlanVerdict = reviewer.run(
            workbook_ctx=ctx, plan=plan, findings=findings,
        )["verdict"]
        if verdict.verdict == "needs_fix":
            # Apply row corrections by replacing the named row's role.
            new_rows = list(plan.rows)
            for corr in verdict.row_corrections:
                for i, r in enumerate(new_rows):
                    if r.idx == corr.get("row"):
                        new_rows[i] = r.model_copy(update={
                            "role": corr.get("suggested_role", r.role),
                            "anchor_idx": corr.get("anchor_idx", r.anchor_idx),
                        })
                        break
            plan = plan.model_copy(update={"rows": new_rows})

    namer = FieldNamer(llm=llm)
    name_map: CanonicalNameMap = namer.run(workbook_ctx=ctx, plan=plan)["name_map"]

    return plan, name_map, warnings


def _signals_from_plan(ctx, plan: SheetPlan):
    """Re-run the surveyor to give the hinter raw signals."""
    from app.services.planner.surveyor import survey_sheet
    return survey_sheet(ctx, plan.sheet)


def extract(workbook_path: Path | str, *, llm=None) -> ExtractionResult:
    t0 = time.monotonic()
    ctx = register_workbook(workbook_path)
    llm = llm or AnthropicProvider.from_env()

    summary = TOOL_REGISTRY.get("workbook_summary")(ctx)
    sc = SheetClassifier(llm=llm)
    relevant = sc.run(workbook_ctx=ctx, workbook_summary=summary)["relevant_sheets"]
    if not relevant:
        return ExtractionResult(
            plis=[], source_file=str(ctx.path),
            warnings=[Warning(message="No relevant sheets identified", severity="warning")],
        )

    all_plis: list[PLI] = []
    all_warnings: list[Warning] = []
    format_detected: str | None = None

    for sheet in relevant:
        plan, name_map, warns = _plan_for_sheet(ctx, sheet, llm)
        all_warnings.extend(warns)
        plis = apply_plan(ctx, plan, name_map)
        for pli in plis:
            if not pli.source.sheet:
                pli.source.sheet = sheet
        all_plis.extend(plis)
        if format_detected is None:
            format_detected = plan.pli_mode.value

    result = ExtractionResult(
        plis=all_plis, warnings=all_warnings,
        format_detected=format_detected, source_file=str(ctx.path),
    )
    src_v = SourceCellVerifier(workbook_ctx=ctx).run(extraction=result)["findings"]
    hdr_v = HeaderMatchVerifier(workbook_ctx=ctx).run(extraction=result)["findings"]
    cov_v = CoverageVerifier(boundaries=[]).run(extraction=result)["findings"]
    drop_v = FieldDropoutVerifier().run(extraction=result)["findings"]
    all_findings = ValidationFindings(findings=(
        src_v.findings + hdr_v.findings + cov_v.findings + drop_v.findings
    ))
    final = reconcile(workflow_out=result, validation_out=all_findings)
    extraction_duration_seconds.labels(
        format_detected=final.format_detected or "unknown"
    ).observe(time.monotonic() - t0)
    extraction_pli_count.labels(source_file=ctx.path.name).set(len(final.plis))
    return final
```

- [ ] **Step 4: Run test, expect PASS**

```
.venv/Scripts/python.exe -m pytest tests/integration/test_extraction_pipeline.py -q
```

- [ ] **Step 5: Run the full suite — there will be old tests that fail because we still need to delete old code. Note which tests fail. Expected: regressions in tests of deleted modules.**

```
.venv/Scripts/python.exe -m pytest tests -q
```

- [ ] **Step 6: Commit**

```bash
git add app/services/extraction.py tests/integration/test_extraction_pipeline.py
git commit -m "feat(extraction): rewrite orchestrator to use SheetRowPlanner"
```

---

## Phase 7 — Cleanup: delete obsolete modules

### Task 23: Delete obsolete agent modules

**Files to delete:**
- `app/services/agents/layout_fingerprinter.py`
- `app/services/agents/boundary_finder.py`
- `app/services/agents/identity_locator.py`
- `app/services/agents/quantity_date_locator.py`
- `app/services/agents/stage_locator.py`
- `app/prompts/workflow/layout_fingerprinter.md`
- `app/prompts/workflow/boundary_finder.md`
- `app/prompts/workflow/identity_locator.md`
- `app/prompts/workflow/quantity_date_locator.md`
- `app/prompts/workflow/stage_locator.md`
- corresponding test files under `tests/unit/agents/` if they exist for these names

- [ ] **Step 1: Confirm no live imports remain**

```
grep -rn "layout_fingerprinter\|boundary_finder\|identity_locator\|quantity_date_locator\|stage_locator" app/ tests/ 2>&1 | grep -v "__pycache__"
```
Expected: zero matches in `app/` (the orchestrator rewrite already removed these). Matches in `tests/` indicate stale tests — delete the test files too.

- [ ] **Step 2: Delete the files**

```
git rm app/services/agents/layout_fingerprinter.py app/services/agents/boundary_finder.py app/services/agents/identity_locator.py app/services/agents/quantity_date_locator.py app/services/agents/stage_locator.py
git rm app/prompts/workflow/layout_fingerprinter.md app/prompts/workflow/boundary_finder.md app/prompts/workflow/identity_locator.md app/prompts/workflow/quantity_date_locator.md app/prompts/workflow/stage_locator.md
git rm tests/unit/agents/test_layout_fingerprinter.py tests/unit/agents/test_boundary_finder.py tests/unit/agents/test_identity_locator.py tests/unit/agents/test_quantity_date_locator.py tests/unit/agents/test_stage_locator.py 2>/dev/null || true
```

- [ ] **Step 3: Run test suite, expect no regressions from the deletion**

```
.venv/Scripts/python.exe -m pytest tests -q
```

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove obsolete LLM agents (replaced by SheetRowPlanner + 3 new agents)"
```

---

### Task 24: Delete obsolete applier modules + enums

**Files to delete:**
- `app/services/applier/field_applier.py`
- `app/services/applier/stage_applier.py`
- `app/services/applier/patterns/__init__.py`
- `app/services/applier/patterns/one_row_per_pli.py`
- `app/services/applier/patterns/vertical_merge.py`
- `app/services/applier/patterns/data_then_total.py`
- `app/services/applier/patterns/one_sheet_per_pli.py`
- `app/services/applier/_registry.py` (the pattern handler registry, NOT the tool registry)
- `app/enums/boundary_pattern.py`
- `app/enums/stage_layout_mode.py`
- corresponding tests

- [ ] **Step 1: Confirm no live imports**

```
grep -rn "field_applier\|stage_applier\|BoundaryPattern\|StageLayoutMode\|services\.applier\.patterns" app/ tests/ 2>&1 | grep -v __pycache__
```

The only matches should be in tests for the deleted modules and the planner files we're keeping for the new pipeline. Audit anything else.

- [ ] **Step 2: Delete the files**

```
git rm app/services/applier/field_applier.py app/services/applier/stage_applier.py
git rm -r app/services/applier/patterns/
git rm app/services/applier/_registry.py 2>/dev/null || true
git rm app/enums/boundary_pattern.py app/enums/stage_layout_mode.py
git rm tests/unit/test_field_applier.py tests/unit/test_stage_applier.py 2>/dev/null || true
```

- [ ] **Step 3: Update `app/services/applier/__init__.py`** to re-export `apply_plan` only

```python
"""Applier package — pure deterministic resolvers."""
from app.services.applier.apply_plan import apply_plan

__all__ = ["apply_plan"]
```

- [ ] **Step 4: Run test suite, expect green**

```
.venv/Scripts/python.exe -m pytest tests -q
```

- [ ] **Step 5: Commit**

```bash
git add app/services/applier/__init__.py
git commit -m "chore: remove field/stage applier, pattern handlers, BoundaryPattern, StageLayoutMode enums"
```

---

## Phase 8 — End-to-end + evals

### Task 25: End-to-end regression test on `CHRISTIAN BERG- T&A.xlsx`

**Files:**
- Test: `tests/regression/test_christian_berg.py`

- [ ] **Step 1: Write test**

```python
# tests/regression/test_christian_berg.py
"""Live regression: CHRISTIAN BERG should produce 7 PLIs."""
import json
from pathlib import Path
import pytest


@pytest.mark.live
def test_christian_berg_seven_plis():
    from app.services.extraction import extract
    p = Path("dataset/CHRISTIAN BERG- T&A.xlsx")
    if not p.exists():
        pytest.skip("dataset file not present")
    result = extract(p)
    label = json.loads(Path("dataset/extracted/CHRISTIAN BERG- T&A.json").read_text())
    assert len(result.plis) == label["total_plis"]
```

- [ ] **Step 2: Run** (skip if dataset/.env missing)

```
.venv/Scripts/python.exe -m pytest tests/regression/test_christian_berg.py -q -m live
```

- [ ] **Step 3: Commit**

```bash
git add tests/regression/test_christian_berg.py
git commit -m "test(regression): CHRISTIAN BERG produces 7 PLIs end-to-end"
```

---

### Task 26: End-to-end regression test on `new job-TNA.xlsx`

**Files:**
- Test: `tests/regression/test_new_job_tna.py`

- [ ] **Step 1: Write test**

```python
# tests/regression/test_new_job_tna.py
"""new job-TNA.xlsx is SHEET_IS_PLI — each of 5 sheets emits 1 PLI."""
from pathlib import Path
import pytest


@pytest.mark.live
def test_new_job_tna_five_plis_one_per_sheet():
    from app.services.extraction import extract
    p = Path("dataset/new job-TNA.xlsx")
    if not p.exists():
        pytest.skip("dataset file not present")
    result = extract(p)
    assert len(result.plis) == 5
    for pli in result.plis:
        assert pli.io_number is not None or pli.metadata.get("io_number") is not None
        assert len(pli.stages) >= 1
```

- [ ] **Step 2: Run**

- [ ] **Step 3: Commit**

```bash
git add tests/regression/test_new_job_tna.py
git commit -m "test(regression): new job-TNA emits 5 PLIs (one per sheet)"
```

---

### Task 27: Run full eval matrix and capture metrics

- [ ] **Step 1: Run evals**

```
make eval
```

or directly:

```
.venv/Scripts/python.exe -m evals.runner --all
```

- [ ] **Step 2: Capture before/after metrics**

Compare field accuracy, stage accuracy, source-cell-match, header-match against the labels under `dataset/extracted/*.json`. Record numbers in a temp scratch file.

- [ ] **Step 3: If any file regressed substantially (>5pp drop in field accuracy), pause and investigate. Otherwise continue.**

- [ ] **Step 4: Commit eval matrix output if there's a tracked output file**

```bash
git add evals/outputs/ 2>/dev/null
git commit -m "eval: capture SheetRowPlanner baseline metrics" 2>/dev/null || true
```

---

## Phase 9 — Documentation

### Task 28: Update `ARCHITECTURE.md`

- [ ] **Step 1: Open `ARCHITECTURE.md` and replace the multi-agent pipeline section to describe the new flow.** The new sections should cover:
  - The three orthogonal axes (PLI scope × Stage scope × PLI height)
  - The `SheetPlan` artifact (rows, blocks, KV anchors, stage bands)
  - LLM-as-judge pattern (PlanReviewer, LayoutHinter, FieldNamer)
  - 100% deterministic `apply_plan`

- [ ] **Step 2: Commit**

```bash
git add ARCHITECTURE.md
git commit -m "docs: rewrite ARCHITECTURE for SheetRowPlanner pipeline"
```

---

### Task 29: Update `docs/SPEC.md`

- [ ] **Step 1: Open `docs/SPEC.md` and update**
  - Phase numbering (Phase 0 → 7)
  - Artifact list (SheetPlan, PliBlock, RowSpec, KVAnchor, StageBandSpec, CanonicalNameMap, LayoutHints, PlanVerdict)
  - Validator list (Tier 1 + Tier 2 plan validators added; the 4 existing extraction validators unchanged)
  - Drop references to BoundaryPattern, StageLayoutMode, pattern handlers, field_applier, stage_applier

- [ ] **Step 2: Commit**

```bash
git add docs/SPEC.md
git commit -m "docs: update SPEC for SheetRowPlanner pipeline"
```

---

### Task 30: Update `README.md` and flip design doc status

- [ ] **Step 1: Update `README.md` if any user-facing wording mentions the removed agents or boundary patterns.**

- [ ] **Step 2: Open `docs/superpowers/specs/2026-05-13-sheet-row-planner-design.md` and flip:**

```
**Status:** Approved, ready for implementation plan
```

to:

```
**Status:** Implemented
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/superpowers/specs/2026-05-13-sheet-row-planner-design.md
git commit -m "docs: mark SheetRowPlanner spec as Implemented"
```

---

## Self-review checklist (run after all tasks complete)

- [ ] CHRISTIAN BERG- T&A.xlsx end-to-end produces 7 PLIs.
- [ ] new job-TNA.xlsx produces 5 PLIs (one per sheet).
- [ ] All previously-passing unit + integration tests still pass.
- [ ] `apply_plan` has no LLM imports (the static test enforces this).
- [ ] Eval matrix shows no regression > 5pp on any dataset file.
- [ ] `ARCHITECTURE.md`, `docs/SPEC.md`, and the design doc status are updated.
- [ ] No code comment/docstring references plan or task numbers.
