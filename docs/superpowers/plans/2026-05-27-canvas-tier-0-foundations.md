# Canvas Architecture — Tier 0: Foundations

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to execute this plan task-by-task.

**Goal:** Land the documentation foundation (ADR + design spec + plans), promote `experiments/specs/` to `app/specs/` with zero behaviour change, and add the typed artifacts (`GridCanvas`, `StructureBag`, `LayoutHint`, `Finding`, `Verdict`, `LayoutAxes`) that subsequent tiers depend on.

**Architecture:** Pure docs + typed artifacts. No tools, no components, no pipelines, no behaviour change. This tier exists so Tier 1 and beyond have types and conventions to import from.

**Tech stack:** No new dependencies. Pydantic 2.6+, dataclasses, openpyxl types for coords.

**Eval expectation:** zero change to canvas_eval (artifacts only).

---

## Conventions

See master plan conventions. Tier 0 specifics:

- All four PRs (0a, 0b, 0c, 0d) target `canvas-architecture` branch
- 0a and 0b are docs-only — no code, no tests
- 0c moves files but doesn't change their content (use `git mv` to preserve history)
- 0d adds new files only; existing code is not touched

---

## Task overview

| PR | # | Task | Type |
|---|---|---|---|
| 0a | 1 | Write design spec (`2026-05-27-canvas-architecture-design.md`) | docs |
| 0a | 2 | Write ADR-0008 (`0008-canvas-architecture.md`) | docs |
| 0a | 3 | Update ARCHITECTURE.md with canvas section | docs |
| 0b | 4 | Write master plan (`2026-05-27-canvas-architecture-master-plan.md`) | docs |
| 0b | 5 | Write Tier 0 plan (this file) | docs |
| 0b | 6 | Write outlines for Tier 1-8 plans | docs |
| 0c | 7 | `git mv experiments/specs/ app/specs/` + import-path updates | refactor |
| 0c | 8 | Add `tests/unit/test_specs_import.py` smoke test | test |
| 0d | 9 | Add `app/artifacts/canvas.py` (GridCanvas) | feat |
| 0d | 10 | Add `app/artifacts/structure.py` (StructureBag + record types) | feat |
| 0d | 11 | Add `app/artifacts/layout.py` (LayoutHint + LayoutAxes) | feat |
| 0d | 12 | Add `app/artifacts/finding.py` (Finding + Verdict + ValidationWarning) | feat |
| 0d | 13 | Re-export new artifacts from `app/artifacts/__init__.py` | feat |
| 0d | 14 | Tests for each artifact (validation, serialisation) | test |

---

## PR 0a — Documentation foundation

### Task 1 — Write design spec

**File:** `docs/superpowers/specs/2026-05-27-canvas-architecture-design.md`

**Status:** ✅ Done — written in this branch on first commit.

Self-review checks for the doc:
- [ ] Covers all five layers (canvas, patterns, resolvers, components, judges)
- [ ] Covers workbook routing
- [ ] Covers per-canonical contracts for all 11 identifiers + stages + metadata
- [ ] Covers PR map and eval bar
- [ ] References ADR-0008 and CODING_STANDARD

### Task 2 — Write ADR-0008

**File:** `docs/adrs/0008-canvas-architecture.md`

**Status:** ✅ Done.

Self-review:
- [ ] Follows ADR-0007 structure (Context, Decision, Why not alternatives, Consequences, Status notes, References)
- [ ] Cross-references design spec

### Task 3 — Update ARCHITECTURE.md

**File:** `ARCHITECTURE.md`

Add a "Canvas Architecture (in development)" section above the existing pipeline section. Two-paragraph summary:
1. What canvas architecture is and why it's being added
2. Pointer to design spec + ADR-0008; note that this is on `canvas-architecture` branch and not merged to main yet

- [ ] Read existing `ARCHITECTURE.md` to find the right insertion point
- [ ] Add ~150-word "Canvas Architecture (in development)" section
- [ ] Link to design spec + ADR-0008
- [ ] Commit: `docs(architecture): add canvas architecture in-development section`

---

## PR 0b — Plan files

### Task 4 — Write master plan

**File:** `docs/superpowers/plans/2026-05-27-canvas-architecture-master-plan.md`

**Status:** ✅ Done.

### Task 5 — Write Tier 0 plan (this file)

**File:** `docs/superpowers/plans/2026-05-27-canvas-tier-0-foundations.md`

**Status:** ✅ Done (you're reading it).

### Task 6 — Write outlines for Tier 1-8 plans

Create one file per tier with header + task overview table only. Tier-specific detail is filled in immediately before the tier starts (this keeps detail fresh).

Files to create (outline-only, ~30-50 lines each):

- `docs/superpowers/plans/2026-05-27-canvas-tier-1-tools.md`
- `docs/superpowers/plans/2026-05-27-canvas-tier-2-structure-phase.md`
- `docs/superpowers/plans/2026-05-27-canvas-tier-3-workbook-phase.md`
- `docs/superpowers/plans/2026-05-27-canvas-tier-4-field-components.md`
- `docs/superpowers/plans/2026-05-27-canvas-tier-5-validators.md`
- `docs/superpowers/plans/2026-05-27-canvas-tier-6-judges.md`
- `docs/superpowers/plans/2026-05-27-canvas-tier-7-pipelines.md`
- `docs/superpowers/plans/2026-05-27-canvas-tier-8-eval-delivery.md`

Each outline has:
1. **Goal** (one paragraph)
2. **Architecture** (one paragraph, pointer to design spec sections)
3. **Eval expectation**
4. **Task overview table** (PR number, task name, type)
5. Note at the bottom: "Detailed task steps written immediately before tier starts."

- [ ] Create all 8 outline files
- [ ] Commit: `docs(plans): add tier 1-8 outlines for canvas architecture`

---

## PR 0c — Promote experiments/specs/ → app/specs/

The specs (FieldSpec, StageSpec, SubfieldSpec, MetadataSpec + enums + schemas) currently live in `experiments/specs/`. They've been used by the canvas probe and are stable. Promote them to `app/specs/` so the rest of the architecture imports from there.

### Task 7 — Move with history

**Files:**
- Move: `experiments/specs/*.py` → `app/specs/*.py`
- Delete: `experiments/specs/` (after moves complete)
- Update: any file under `experiments/p3_visual/canvas_probe/` that imports from `experiments.specs.*`

**Steps:**

- [ ] **7.1 Inventory current `experiments/specs/`**

  Run: `ls experiments/specs/`
  Expected files: `enums.py`, `schemas.py`, `identifiers.py`, `stages.py`, `subfields.py`, `metadata.py`, `prompts.py`, `render.py`, `__init__.py`

- [ ] **7.2 Move files via git**

  ```
  mkdir -p app/specs
  git mv experiments/specs/enums.py        app/specs/enums.py
  git mv experiments/specs/schemas.py      app/specs/schemas.py
  git mv experiments/specs/identifiers.py  app/specs/identifiers.py
  git mv experiments/specs/stages.py       app/specs/stages.py
  git mv experiments/specs/subfields.py    app/specs/subfields.py
  git mv experiments/specs/metadata.py     app/specs/metadata.py
  git mv experiments/specs/prompts.py      app/specs/prompts.py
  git mv experiments/specs/render.py       app/specs/render.py
  git mv experiments/specs/__init__.py     app/specs/__init__.py
  ```

- [ ] **7.3 Update import paths within moved files**

  `git grep -l "from specs\." app/specs/ experiments/p3_visual/`
  Replace `from specs.` with `from app.specs.` in each match.

- [ ] **7.4 Update sys.path injection in experiments/p3_visual/canvas_probe/**

  `experiments/p3_visual/canvas_probe/spec_queries.py` has:
  ```python
  _EXP_ROOT = Path(__file__).resolve().parent.parent.parent
  sys.path.insert(0, str(_EXP_ROOT))
  from specs.identifiers import IDENTIFIER_SPECS
  ```

  Replace with:
  ```python
  from app.specs.identifiers import IDENTIFIER_SPECS
  ```

  (No sys.path injection needed since `app/` is on the path.)

- [ ] **7.5 Verify no broken imports**

  ```
  /Users/nagasai/Documents/DAITA/tna-service/.venv/bin/python -c "
  from app.specs.identifiers import IDENTIFIER_SPECS
  from app.specs.stages import STAGE_SPECS
  from app.specs.subfields import SUBFIELD_SPECS
  from app.specs.metadata import METADATA_SPECS
  from app.specs.enums import Area, LabelMatchMode, ValueDtype
  from app.specs.schemas import FieldSpec
  print('OK')
  "
  ```
  Expected output: `OK`

- [ ] **7.6 Run experiments canvas eval to confirm parity**

  ```
  /Users/nagasai/Documents/DAITA/tna-service/.venv/bin/python experiments/canvas_eval/score.py | tail -5
  ```

  Expected: same totals as before (recall 68.1%, precision 65.2%).

- [ ] **7.7 Commit**

  ```
  git commit -m "refactor(specs): promote experiments/specs to app/specs

  Moves FieldSpec/StageSpec/SubfieldSpec/MetadataSpec and registries from
  experiments/specs/ to app/specs/. Updates imports in
  experiments/p3_visual/canvas_probe/ to use new location.

  No behaviour change. Canvas eval against extracted_2 unchanged at 68.1%
  recall / 65.2% precision.

  CODING_STANDARD self-review:
  - S5 modern type hints: existing code unchanged (already compliant)
  - S7 import groups: updates use absolute imports only
  - S8 module layout: app/specs/ has one responsibility (field/stage/metadata specs)
  - S11 primitive home: specs at app/specs/ matches ADR-0007 convention"
  ```

### Task 8 — Smoke test

**File:** `tests/unit/specs/test_import.py`

- [ ] **8.1 Write the test**

  ```python
  """Smoke tests proving app.specs is importable and registries are populated."""
  from __future__ import annotations


  def test_identifier_specs_loaded() -> None:
      """All 11 identifier specs must be present."""
      from app.specs.identifiers import IDENTIFIER_SPECS
      canonicals = {s.canonical for s in IDENTIFIER_SPECS}
      expected = {
          "io_number", "style_code", "style_name",
          "color_code", "color_name",
          "fabric_code", "fabric_name",
          "quantity",
          "delivery_date", "shipment_date", "ex_fty_date",
      }
      assert canonicals == expected


  def test_stage_specs_loaded() -> None:
      """Stage spec registry must include the new VAP, line_plan, feeding entries."""
      from app.specs.stages import STAGE_SPECS
      canonicals = {s.canonical for s in STAGE_SPECS}
      assert "fabric" in canonicals
      assert "vap" in canonicals
      assert "line_plan" in canonicals
      assert "feeding" in canonicals


  def test_subfield_specs_loaded() -> None:
      """Subfield registry must include status (added during canvas eval)."""
      from app.specs.subfields import SUBFIELD_SPECS
      canonicals = {s.canonical for s in SUBFIELD_SPECS}
      assert "status" in canonicals
      assert "planned_date" in canonicals
      assert "actual_date" in canonicals
  ```

- [ ] **8.2 Run the test**

  ```
  pytest tests/unit/specs/test_import.py -v
  ```

  Expected: 3 passed.

- [ ] **8.3 Commit**

  ```
  git commit -m "test(specs): smoke test that app.specs registries are loaded"
  ```

---

## PR 0d — Artifacts module

Adds the typed dataclasses that Tier 1-8 depend on. These are the "off-canvas vocabulary" the design spec describes: small record types pointing into canvas channels by coordinate.

### Task 9 — `app/artifacts/canvas.py`

**File:** `app/artifacts/canvas.py`

The `GridCanvas` typed wrapper. The existing `experiments/p3_visual/canvas_probe/build_canvas.py` has a `GridCanvas` dataclass already; this task wraps it as a first-class artifact at the proper home.

- [ ] **9.1 Write the failing test**

  `tests/unit/artifacts/test_canvas.py`:
  ```python
  """GridCanvas artifact must accept channels and cell_values dicts."""
  from __future__ import annotations

  from app.artifacts.canvas import GridCanvas


  def test_canvas_construction() -> None:
      """A GridCanvas with empty channels and 3x3 cell_values constructs cleanly."""
      canvas = GridCanvas(
          n_rows=3,
          n_cols=3,
          cell_values=[[None]*3 for _ in range(3)],
          channels={},
          merge_ranges=set(),
      )
      assert canvas.n_rows == 3
      assert canvas.n_cols == 3
      assert canvas.cell_values == [[None]*3 for _ in range(3)]


  def test_add_channel() -> None:
      """add_channel installs a 2D matrix on the canvas."""
      canvas = GridCanvas(n_rows=2, n_cols=2, cell_values=[[None]*2]*2,
                         channels={}, merge_ranges=set())
      canvas.add_channel("dtype", [[0, 0], [0, 0]])
      assert canvas.channels["dtype"] == [[0, 0], [0, 0]]
  ```

- [ ] **9.2 Run the test**

  Expected: failure with `ModuleNotFoundError` for `app.artifacts.canvas`.

- [ ] **9.3 Write the implementation**

  ```python
  """GridCanvas typed artifact: spatial substrate for canvas-based extraction."""
  from __future__ import annotations

  from dataclasses import dataclass, field
  from typing import Any


  @dataclass
  class GridCanvas:
      """A 2D substrate carrying per-cell measurements as named channels.

      Each channel is an n_rows × n_cols matrix indexed in the same coordinate
      space as the sheet (1-indexed externally; 0-indexed in the matrices).
      Tools and components write derived channels back onto the canvas while
      also emitting typed records for iteration.
      """
      n_rows:       int
      n_cols:       int
      cell_values:  list[list[Any]]
      channels:     dict[str, list[list[int]]] = field(default_factory=dict)
      merge_ranges: set[tuple[int, int, int, int]] = field(default_factory=set)

      def add_channel(self, name: str, matrix: list[list[int]]) -> None:
          """Install a new channel under `name`. Caller owns shape correctness."""
          self.channels[name] = matrix
  ```

- [ ] **9.4 Run the test again**

  Expected: 2 passed.

- [ ] **9.5 Apply CODING_STANDARD self-review**

  Run through Section 10 checklist for this file.

### Task 10 — `app/artifacts/structure.py`

**File:** `app/artifacts/structure.py`

Holds `StructureBag` and all pattern/semantic record types.

- [ ] **10.1 Test stub**

  `tests/unit/artifacts/test_structure.py`:
  ```python
  """StructureBag must hold typed records by category."""
  from __future__ import annotations

  from app.artifacts.structure import (
      StructureBag, DateStrip, MergeSpan, ColorStrip, BorderedBox,
      KvBlock, RepeatingRowGroup, HeaderBand, DataRowRange, StageArena,
      StageBand, SubfieldCluster, SectionBoundary,
  )


  def test_empty_bag() -> None:
      """A fresh StructureBag has empty lists for every record type."""
      bag = StructureBag()
      assert bag.date_strips == []
      assert bag.merge_spans == []
      assert bag.kv_blocks == []
      assert bag.header_band is None
  ```

- [ ] **10.2 Implementation**

  Records to define (all dataclasses, frozen where appropriate):
  - `DateStrip(rect, orientation, density)`
  - `IntStrip(rect, magnitude, density)` where `magnitude in {"small","medium","large"}`
  - `FloatStrip(rect, density)`
  - `SameLengthStrip(rect, length, density)`
  - `LongTextStrip(rect, mean_length)`
  - `ColorStrip(rect, orientation, color)`
  - `BoldStrip(rect, orientation)`
  - `BorderedBox(rect)`
  - `MergeSpan(rect, orientation)` where `orientation in {"horizontal","vertical","block"}`
  - `NonMergedStrip(rect, orientation)`
  - `MergedColumnStrip(rect, merge_count)`
  - `KvBlock(label_coord, value_coord, label_text, value_dtype)`
  - `RepeatingRowGroup(row_indices, signature)`
  - `PlanMarkerCluster(cells)`
  - `HeaderBand(rect, score)`
  - `DataRowRange(row_start, row_end)`
  - `SectionBoundary(start_row, end_row, section_id)`
  - `StageArena(rect)`
  - `StageBand(rect, name_coord, name_text)`
  - `SubfieldCluster(parent_band_id, subfield_coords)`

  And the bag itself:
  ```python
  @dataclass
  class StructureBag:
      date_strips:        list[DateStrip] = field(default_factory=list)
      int_strips:         list[IntStrip] = field(default_factory=list)
      float_strips:       list[FloatStrip] = field(default_factory=list)
      same_length_strips: list[SameLengthStrip] = field(default_factory=list)
      long_text_strips:   list[LongTextStrip] = field(default_factory=list)
      color_strips:       list[ColorStrip] = field(default_factory=list)
      bold_strips:        list[BoldStrip] = field(default_factory=list)
      bordered_boxes:     list[BorderedBox] = field(default_factory=list)
      merge_spans:        list[MergeSpan] = field(default_factory=list)
      non_merged_strips:  list[NonMergedStrip] = field(default_factory=list)
      merged_col_strips:  list[MergedColumnStrip] = field(default_factory=list)
      kv_blocks:          list[KvBlock] = field(default_factory=list)
      repeating_groups:   list[RepeatingRowGroup] = field(default_factory=list)
      plan_marker_clusters: list[PlanMarkerCluster] = field(default_factory=list)
      header_band:        HeaderBand | None = None
      data_row_ranges:    list[DataRowRange] = field(default_factory=list)
      section_boundaries: list[SectionBoundary] = field(default_factory=list)
      stage_arenas:       list[StageArena] = field(default_factory=list)
      stage_bands:        list[StageBand] = field(default_factory=list)
      subfield_clusters:  list[SubfieldCluster] = field(default_factory=list)
  ```

  Also define `Rect` and `Direction` as helper types:
  ```python
  @dataclass(frozen=True)
  class Rect:
      r0: int  # 1-indexed inclusive
      c0: int
      r1: int
      c1: int

      @property
      def area(self) -> int:
          return (self.r1 - self.r0 + 1) * (self.c1 - self.c0 + 1)


  Direction = Literal["vertical", "horizontal", "block"]
  ```

- [ ] **10.3 Run tests, commit**

### Task 11 — `app/artifacts/layout.py`

**File:** `app/artifacts/layout.py`

`LayoutHint` and `LayoutAxes`. The bridge artifact between StructurePhase and field components.

- [ ] **11.1 Test stub** in `tests/unit/artifacts/test_layout.py`

  ```python
  def test_layout_axes_construction() -> None:
      """LayoutAxes accepts the three axis values and per-axis confidence."""
      axes = LayoutAxes(
          pli_axis="vertical",
          stage_axis="horizontal",
          subfield_axis="horizontal",
          confidence={"pli": 0.9, "stage": 0.8, "subfield": 0.7},
      )
      assert axes.pli_axis == "vertical"


  def test_layout_hint_default_candidates() -> None:
      """A new LayoutHint has empty candidate dicts."""
      hint = LayoutHint(
          axes=LayoutAxes(pli_axis="vertical", stage_axis="horizontal",
                           subfield_axis="horizontal", confidence={}),
          cluster_id="test-cluster",
          confidence=0.9,
      )
      assert hint.candidate_columns == {}
      assert hint.candidate_kv_blocks == {}
  ```

- [ ] **11.2 Implementation**

  ```python
  """LayoutHint and LayoutAxes: artifacts emitted by StructurePhase."""
  from __future__ import annotations

  from dataclasses import dataclass, field
  from typing import Callable, Iterator, Literal

  from app.artifacts.structure import (
      HeaderBand, DataRowRange, SectionBoundary,
      StageArena, StageBand, SubfieldCluster, KvBlock,
  )


  Direction = Literal["vertical", "horizontal", "sheet", "sectional", "none", "implicit"]


  @dataclass
  class LayoutAxes:
      """Three orthogonal axes describing how a sheet is laid out."""
      pli_axis:       Direction
      stage_axis:     Direction
      subfield_axis:  Direction
      confidence:     dict[str, float]


  @dataclass
  class LayoutHint:
      """All structural facts a field component needs to extract from a sheet.

      Shared across sheets within a pli_cluster (one LayoutHint per cluster,
      anchored to the cluster's template). Field components consume typed
      records here; they do not reach into raw canvas channels for spatial
      reasoning.
      """
      axes:                LayoutAxes
      cluster_id:          str
      confidence:          float

      header_band:         HeaderBand | None = None
      data_row_ranges:     list[DataRowRange] = field(default_factory=list)
      section_boundaries:  list[SectionBoundary] = field(default_factory=list)
      stage_arenas:        list[StageArena] = field(default_factory=list)
      stage_bands:         list[StageBand] = field(default_factory=list)
      subfield_clusters:   list[SubfieldCluster] = field(default_factory=list)
      kv_blocks:           list[KvBlock] = field(default_factory=list)

      candidate_columns:   dict[str, list[int]] = field(default_factory=dict)
      candidate_rows:      dict[str, list[int]] = field(default_factory=dict)
      candidate_kv_blocks: dict[str, list[KvBlock]] = field(default_factory=dict)
  ```

- [ ] **11.3 Run tests, commit**

### Task 12 — `app/artifacts/finding.py`

**File:** `app/artifacts/finding.py`

`Finding`, `Verdict`, `ValidationWarning`, `Confidence`.

- [ ] **12.1 Test stub**

  ```python
  def test_finding_construction() -> None:
      """A Finding accepts canonical + coords + value + confidence + evidence."""
      f = Finding(
          canonical="io_number",
          label_coord=("K", 2),
          value_coord=("K", 4),
          value="131673",
          confidence=Confidence.HIGH,
          evidence=[],
      )
      assert f.canonical == "io_number"
      assert f.value == "131673"


  def test_verdict_decisions() -> None:
      v = Verdict(decision="keep", reason="confidence-high")
      assert v.decision == "keep"
  ```

- [ ] **12.2 Implementation**

  ```python
  """Finding / Verdict / ValidationWarning — off-canvas typed records."""
  from __future__ import annotations

  from dataclasses import dataclass, field
  from enum import Enum
  from typing import Any, Literal


  Coord = tuple[str, int]  # (column letter, 1-indexed row)


  class Confidence(str, Enum):
      HIGH = "high"
      MEDIUM = "medium"
      LOW = "low"


  @dataclass
  class Finding:
      """One extracted field value with its source coordinates and evidence trail.

      Findings are the unit of currency between field components, validators,
      and judges. Coordinates point into the canvas; the value is the
      extracted content. Evidence carries structural facts that supported
      this finding (e.g. HEADER_BAND_MEMBER, SAME_LENGTH_STRIP, DTYPE_MATCH).
      """
      canonical:    str
      label_coord:  Coord
      value_coord:  Coord
      value:        Any
      confidence:   Confidence
      evidence:     list[str] = field(default_factory=list)
      decision_notes: str | None = None


  @dataclass
  class Verdict:
      """LLM judge output for one ambiguous finding."""
      decision:          Literal["keep", "drop", "rewrite"]
      reason:            str
      alternative_coord: Coord | None = None
      confidence:        Confidence = Confidence.MEDIUM


  @dataclass
  class ValidationWarning:
      """Structural-query validator output flagging a constraint violation."""
      name:     str
      severity: Literal["info", "warning", "error"]
      message:  str
      affects_findings: list[Finding] = field(default_factory=list)

      def affects(self, finding: Finding) -> bool:
          """Return True if this warning concerns the given finding."""
          return finding in self.affects_findings
  ```

- [ ] **12.3 Run tests, commit**

### Task 13 — Re-export from `app/artifacts/__init__.py`

**File:** `app/artifacts/__init__.py`

Add re-exports for the new types so callers can `from app.artifacts import GridCanvas, LayoutHint, Finding, ...`.

- [ ] **13.1 Edit `__init__.py`**

  Add (preserving existing re-exports if any):
  ```python
  from app.artifacts.canvas import GridCanvas
  from app.artifacts.finding import Confidence, Finding, ValidationWarning, Verdict
  from app.artifacts.layout import Direction, LayoutAxes, LayoutHint
  from app.artifacts.structure import (
      BoldStrip, BorderedBox, ColorStrip, DataRowRange, DateStrip, FloatStrip,
      HeaderBand, IntStrip, KvBlock, LongTextStrip, MergeSpan, MergedColumnStrip,
      NonMergedStrip, PlanMarkerCluster, Rect, RepeatingRowGroup,
      SameLengthStrip, SectionBoundary, StageArena, StageBand, StructureBag,
      SubfieldCluster,
  )

  __all__ = [
      "BoldStrip", "BorderedBox", "ColorStrip", "Confidence",
      "DataRowRange", "DateStrip", "Direction", "Finding", "FloatStrip",
      "GridCanvas", "HeaderBand", "IntStrip", "KvBlock", "LayoutAxes",
      "LayoutHint", "LongTextStrip", "MergeSpan", "MergedColumnStrip",
      "NonMergedStrip", "PlanMarkerCluster", "Rect", "RepeatingRowGroup",
      "SameLengthStrip", "SectionBoundary", "StageArena", "StageBand",
      "StructureBag", "SubfieldCluster", "ValidationWarning", "Verdict",
  ]
  ```

- [ ] **13.2 Test that re-exports work**

  ```python
  from app.artifacts import GridCanvas, LayoutHint, Finding, StructureBag
  ```
  must succeed.

- [ ] **13.3 Commit**

### Task 14 — Tests pass

- [ ] **14.1 Run full test suite**

  `pytest tests -q -m "not live"`

  Expected: all existing tests + the new artifact tests pass.

- [ ] **14.2 Commit final**

  ```
  git commit -m "feat(artifacts): add canvas, structure, layout, finding artifacts

  Adds GridCanvas, StructureBag (+ pattern/semantic records), LayoutHint
  (+ LayoutAxes), Finding (+ Confidence/Verdict/ValidationWarning) and
  re-exports them from app.artifacts.

  No existing code touched. Subsequent tiers consume these as the typed
  vocabulary between layers.

  CODING_STANDARD self-review:
  - S3 docstrings on every public class
  - S5 modern type hints throughout
  - S7 three import groups, absolute imports
  - S8 one responsibility per module
  - S11 artifacts home matches ADR-0007 convention"
  ```

---

## Tier 0 exit bar

- [ ] All 4 PRs (0a, 0b, 0c, 0d) merged into `canvas-architecture`
- [ ] `make test` passes (252 + new artifact tests)
- [ ] `experiments/canvas_eval/score.py` still produces 68.1% recall / 65.2% precision (no regression)
- [ ] Master plan checklist updated with Tier 0 ✓
- [ ] No code under `app/components/`, `app/tools/canvas/`, `app/pipelines/canvas/` exists yet — those are Tier 1+ territory
- [ ] Legacy SheetRowPlanner path untouched on `main`

When all six items are checked, Tier 0 is complete and Tier 1 can start.
