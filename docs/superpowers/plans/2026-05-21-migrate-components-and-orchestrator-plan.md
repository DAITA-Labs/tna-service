# Migrate Components & Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move tools, planner sub-components, applier, reconciler, and validators from `app/services/` and `app/repositories/workbook_tools/` to the new substrate. Convert the orchestrator from imperative Python to a Haystack `Pipeline` factory. Add the new between-agents validators that close the multi-point-failure gap. Retire `app/services/` entirely.

**Architecture:** Haystack `Pipeline` with `pipeline.connect()` edges replaces the imperative orchestrator. Each migrated unit becomes a `Component` subclass (Haystack `@component` decorated via our base). New "between-agents" validators sit between/after LLM components to re-validate after each LLM-driven mutation to plan/name_map. ADR-0007 records the architectural shift; ARCHITECTURE.md is rewritten to match.

**Tech Stack:** Python 3.12, Haystack 2.10+ (Pipeline + tracer load-bearing), Pydantic 2.6+, OpenTelemetry SDK 1.27+.

---

## Conventions (engineer: read once, apply to every task)

- Python 3.12+, modern types (`list[X]`, `X | None`; no `Optional`/`List`/`Dict`/`Union` from `typing`).
- `from __future__ import annotations` at the top of every new file.
- One-line imperative docstrings on every public function, class, and module.
- Function bodies ≤ 40 lines (CODING_STANDARD §2); use `# allow-long: <reason>` only when one cohesive concept demonstrably can't be split.
- No narrative comments — only constraint / workaround / external-reference comments.
- No plan-task names (`# task 17`, `# Phase F`) inside production code.
- Conventional commits, one commit per task (`feat:`, `refactor:`, `test:`, `chore:`, `docs:`).
- After every commit, `make test` (i.e. `pytest -q -m "not live"`) must pass.
- After every phase checkpoint, `make test` AND `make eval-smoke` must pass.
- Full `make eval` matrix compared to a pre-migration baseline at the end of Phase F — must match within noise (≤ 1 pp drift on field_precision_recall, pli_recall, stage_recall).
- All paths absolute from repo root.
- Sub-plans 1–4 are assumed landed: `app/pipelines/_base.py:make_pipeline`, `app/components/_base.py:Component`, `app/agents/_base.py:Agent`, `app/inferencing/{_base,anthropic}.py`, `app/tools/{_registry,_decorator}.py`, `app/artifacts/__init__.py`, and the 4 migrated agents under `app/agents/<name>/` exist before this plan starts.

---

## Task overview

| # | Task | Type |
|---|---|---|
| **Phase A — Tools migration** | | |
| A.1 | Snapshot pre-migration eval baseline | chore |
| A.2 | Move `survey.py` tools (`list_sheets`, `workbook_summary`) | refactor |
| A.3 | Move `bulk_read.py` tools (`peek_sheet`, `sample_rows`, `read_range`) + shared `_cell` helper | refactor |
| A.4 | Move `targeted.py` tools (`read_row`, `read_relative`, `get_cell_at`) | refactor |
| A.5 | Move `structure.py` tools (`get_merged_regions`, `count_non_empty_rows_in_column`) | refactor |
| A.6 | Move `search.py` tool (`find_value`) | refactor |
| A.7 | Rewrite tool callers (orchestrator + planner sub-components + agents) onto `app.tools` | refactor |
| A.8 | **Checkpoint A** — `make test` + `make eval-smoke` | chore |
| **Phase B — Planner sub-components** | | |
| B.1 | Wrap `surveyor` as `app/components/planner/surveyor.py` Component | refactor |
| B.2 | Wrap `row_classifier` as `app/components/planner/row_classifier.py` Component | refactor |
| B.3 | Wrap `kv_anchor_detector` as `app/components/planner/kv_anchor_detector.py` Component | refactor |
| B.4 | Wrap `stage_band_detector` as `app/components/planner/stage_band_detector.py` Component | refactor |
| B.5 | Wrap `block_segmenter` as `app/components/planner/block_segmenter.py` Component | refactor |
| B.6 | Move `SheetRowPlanner` to `app/components/planner/plan.py` + rewire imports | refactor |
| B.7 | **Checkpoint B** — `make test` + `make eval-smoke` | chore |
| **Phase C — Existing validators** | | |
| C.1 | Move `plan_invariants` → `app/components/validators/plan_invariants.py` (Component wrap) | refactor |
| C.2 | Move `plan_statistics` → `app/components/validators/plan_statistics.py` (Component wrap) | refactor |
| C.3 | Move `coverage_verifier` (already @component) → `app/components/validators/coverage_verifier.py` | refactor |
| C.4 | Move `field_dropout_verifier` → `app/components/validators/field_dropout_verifier.py` | refactor |
| C.5 | Move `header_match_verifier` → `app/components/validators/header_match_verifier.py` | refactor |
| C.6 | Move `source_cell_verifier` → `app/components/validators/source_cell_verifier.py` | refactor |
| C.7 | **Checkpoint C** — `make test` + `make eval-smoke` | chore |
| **Phase D — New between-agents validators** | | |
| D.1 | `post_review_plan` validator (failing test) | test |
| D.2 | `post_review_plan` Component impl | feat |
| D.3 | `post_namer_canonical` validator (failing test) | test |
| D.4 | `post_namer_canonical` Component impl | feat |
| D.5 | `pre_apply_readiness` validator (failing test) | test |
| D.6 | `pre_apply_readiness` Component impl | feat |
| D.7 | **Checkpoint D** — `make test` + `make eval-smoke` | chore |
| **Phase E — Applier + reconciler** | | |
| E.1 | Move `apply_plan` → `app/components/applier.py` Component | refactor |
| E.2 | Move `reconcile` → `app/components/reconciler.py` Component | refactor |
| E.3 | Static-import-guard test: applier still LLM-free | test |
| E.4 | **Checkpoint E** — `make test` + `make eval-smoke` | chore |
| **Phase F — Haystack Pipeline factory** | | |
| F.1 | Add `HAYSTACK_CONTENT_TRACING_ENABLED=true` to dev/test config | feat |
| F.2 | Failing wiring test for `make_extract_pipeline` | test |
| F.3 | `app/pipelines/extract.py` — `make_extract_pipeline(llm, tuning) -> Pipeline` | feat |
| F.4 | Per-sheet driver `extract(workbook_path, *, llm=None) -> ExtractionResult` wrapping the pipeline + preserving root `extract` OTel span | feat |
| F.5 | Haystack content-tracing per-component span test | test |
| F.6 | **Checkpoint F** — `make test` + `make eval-smoke` + full `make eval` baseline diff | chore |
| **Phase G — Router** | | |
| G.1 | Rewrite `app/routers/extract.py` import to `app.pipelines.extract` | refactor |
| G.2 | **Checkpoint G** — `make test` (router contract preserved) | chore |
| **Phase H — Cleanup** | | |
| H.1 | Delete `app/services/` (planner/, validation/, applier/, reconciler.py, extraction.py — agents/ + llm_provider.py removed by sub-plans 2/4) | chore |
| H.2 | Delete `app/repositories/workbook_tools/` | chore |
| H.3 | Delete `app/prompts/workflow/` (replaced by `app/prompts/<name>.py` modules in sub-plan 4) | chore |
| **Phase I — Documentation + ADR** | | |
| I.1 | Add ADR-0007 `docs/adrs/0007-pipeline-architecture-redesign.md` | docs |
| I.2 | Rewrite `ARCHITECTURE.md` (Layered structure → seven-primitive view; phase diagram → Haystack Pipeline wiring; extension matrix) | docs |
| I.3 | Add §11 (Framework primitives) to `docs/CODING_STANDARD.md` + §10 checklist additions | docs |
| I.4 | Cross-reference Principles 4 + 11 in `docs/PRINCIPLES.md`; verify Principles 12 + 13 are present | docs |

Total: 45 tasks.

---

# Phase A — Tools migration

## Task A.1 — Snapshot pre-migration eval baseline

**Files:**
- Create: `evals/runs/baseline-pre-pipeline-migration.json` (output of `make eval`)

- [ ] **A.1.1 Run baseline eval.**

```bash
make eval
cp evals/runs/$(ls -1t evals/runs/ | head -1) evals/runs/baseline-pre-pipeline-migration.json
```

- [ ] **A.1.2 Commit the baseline.**

```bash
git add evals/runs/baseline-pre-pipeline-migration.json
git commit -m "chore(eval): capture pre-pipeline-migration baseline matrix"
```

This baseline is the regression gate that Phase F's full `make eval` run is compared against.

---

## Task A.2 — Move `survey` tools to `app/tools/survey.py`

**Files:**
- Create: `app/tools/survey.py`
- Test: `tests/unit/tools/test_survey.py`

The new `@tool` decorator (from `app/tools/_decorator.py`) is the sole registration site. The old `_registry.py` will be deleted in Phase H.

- [ ] **A.2.1 Write failing test.**

```python
"""Unit tests for survey tools after migration."""
from __future__ import annotations
from pathlib import Path
import pytest
from app.repositories.workbook_repo import register_workbook
from app.tools import get_tool


def test_list_sheets_returns_meta(sample_xlsx: Path) -> None:
    """list_sheets returns one SheetMeta per workbook sheet."""
    ctx = register_workbook(sample_xlsx)
    sheets = get_tool("list_sheets")(ctx)
    assert len(sheets) == len(ctx.wb.sheetnames)
    assert all(hasattr(s, "max_row") for s in sheets)


def test_workbook_summary_returns_counts(sample_xlsx: Path) -> None:
    """workbook_summary reports sheet count + names + size."""
    ctx = register_workbook(sample_xlsx)
    summary = get_tool("workbook_summary")(ctx)
    assert summary.sheet_count == len(ctx.wb.sheetnames)
```

- [ ] **A.2.2 Run pytest** — expect `KeyError: tool 'list_sheets' not registered`.

- [ ] **A.2.3 Implement.**

```python
"""Survey tools — cheap, no cell reads."""
from __future__ import annotations

from app.models.artifacts import WorkbookSummary
from app.models.workbook import SheetMeta, WorkbookCtx
from app.tools import tool


@tool("list_sheets")
def list_sheets(ctx: WorkbookCtx) -> list[SheetMeta]:
    """Return name + dimensions for every sheet in the workbook."""
    out: list[SheetMeta] = []
    for name in ctx.wb.sheetnames:
        ws = ctx.wb[name]
        out.append(SheetMeta(
            name=name,
            max_row=ws.max_row or 0,
            max_col=ws.max_column or 0,
            dimensions=ws.dimensions,
        ))
    return out


@tool("workbook_summary")
def workbook_summary(ctx: WorkbookCtx) -> WorkbookSummary:
    """Return a high-level shape summary of the workbook."""
    size_kb = ctx.path.stat().st_size // 1024
    return WorkbookSummary(
        sheet_count=len(ctx.wb.sheetnames),
        sheet_names=list(ctx.wb.sheetnames),
        file_size_kb=size_kb,
    )
```

- [ ] **A.2.4 Re-run pytest** — green.

- [ ] **A.2.5 Commit.**

```bash
git add app/tools/survey.py tests/unit/tools/test_survey.py
git commit -m "refactor(tools): move survey tools to app/tools/survey.py"
```

---

## Task A.3 — Move `bulk_read` tools (shared `_cell` helper)

**Files:**
- Create: `app/tools/bulk_read.py`
- Test: `tests/unit/tools/test_bulk_read.py`

`_cell` and `_infer_dtype` move alongside as private helpers (still imported by `targeted.py`).

- [ ] **A.3.1 Write failing test.**

```python
"""Unit tests for bulk_read tools after migration."""
from __future__ import annotations
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from app.tools import get_tool


def test_peek_sheet_returns_top_left(sample_xlsx: Path) -> None:
    """peek_sheet returns a bounded CellGrid for the top-left window."""
    ctx = register_workbook(sample_xlsx)
    grid = get_tool("peek_sheet")(ctx, sheet=ctx.wb.sheetnames[0], rows=5, cols=5)
    assert grid.sheet == ctx.wb.sheetnames[0]
    assert grid.cell_range.startswith("A1:")


def test_sample_rows_returns_per_row_cells(sample_xlsx: Path) -> None:
    """sample_rows returns one list of non-empty Cell per requested row."""
    ctx = register_workbook(sample_xlsx)
    rows = get_tool("sample_rows")(ctx, sheet=ctx.wb.sheetnames[0], row_indices=[1, 2])
    assert len(rows) == 2


def test_read_range_returns_window(sample_xlsx: Path) -> None:
    """read_range returns a CellGrid bounded by the requested row+col range."""
    ctx = register_workbook(sample_xlsx)
    grid = get_tool("read_range")(ctx, sheet=ctx.wb.sheetnames[0],
                                  row_range=(1, 3), col_range=(1, 3))
    assert ":" in grid.cell_range
```

- [ ] **A.3.2 Run pytest** — failure.

- [ ] **A.3.3 Implement.**

```python
"""Bulk-read tools — bounded windows over a sheet."""
from __future__ import annotations

from datetime import date, datetime

from openpyxl.utils import get_column_letter

from app.enums.cell_dtype import CellDtype
from app.models.workbook import Cell, CellGrid, WorkbookCtx
from app.tools import tool


def _infer_dtype(v: object) -> CellDtype:
    """Map a raw openpyxl cell value to its CellDtype tag."""
    if v is None:
        return CellDtype.EMPTY
    if isinstance(v, bool):
        return CellDtype.BOOL
    if isinstance(v, int):
        return CellDtype.INT
    if isinstance(v, float):
        return CellDtype.FLOAT
    if isinstance(v, (date, datetime)):
        return CellDtype.DATE
    if isinstance(v, str) and v.startswith("#") and v.endswith("!"):
        return CellDtype.ERROR
    return CellDtype.STR


def _cell(ws: object, row: int, col: int) -> Cell:
    """Build a `Cell` for `(row, col)` in `ws` with inferred dtype."""
    raw = ws.cell(row=row, column=col).value
    addr = f"{get_column_letter(col)}{row}"
    return Cell(row=row, col=col, address=addr, value=raw, dtype=_infer_dtype(raw))


@tool("peek_sheet")
def peek_sheet(ctx: WorkbookCtx, sheet: str, rows: int = 10, cols: int = 15) -> CellGrid:
    """Top-left peek over a bounded window; useful for header + early-data probes."""
    ws = ctx.wb[sheet]
    max_r = min(rows, ws.max_row or rows)
    max_c = min(cols, ws.max_column or cols)
    cells: list[Cell] = []
    for r in range(1, max_r + 1):
        for c in range(1, max_c + 1):
            cell = _cell(ws, r, c)
            if cell.value is not None:
                cells.append(cell)
    return CellGrid(sheet=sheet,
                    cell_range=f"A1:{get_column_letter(max_c)}{max_r}",
                    cells=cells)


@tool("sample_rows")
def sample_rows(ctx: WorkbookCtx, sheet: str, row_indices: list[int]) -> list[list[Cell]]:
    """Read every non-empty cell in each row in `row_indices`."""
    ws = ctx.wb[sheet]
    max_c = ws.max_column or 0
    out: list[list[Cell]] = []
    for r in row_indices:
        row_cells = [_cell(ws, r, c) for c in range(1, max_c + 1)]
        out.append([c for c in row_cells if c.value is not None])
    return out


@tool("read_range")
def read_range(ctx: WorkbookCtx, sheet: str,
               row_range: tuple[int, int], col_range: tuple[int, int]) -> CellGrid:
    """Read every non-empty cell in `row_range × col_range`, inclusive."""
    ws = ctx.wb[sheet]
    r0, r1 = row_range
    c0, c1 = col_range
    cells: list[Cell] = []
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            cell = _cell(ws, r, c)
            if cell.value is not None:
                cells.append(cell)
    return CellGrid(sheet=sheet,
                    cell_range=f"{get_column_letter(c0)}{r0}:{get_column_letter(c1)}{r1}",
                    cells=cells)
```

- [ ] **A.3.4 Re-run pytest** — green.

- [ ] **A.3.5 Commit.**

```bash
git add app/tools/bulk_read.py tests/unit/tools/test_bulk_read.py
git commit -m "refactor(tools): move bulk_read tools to app/tools/bulk_read.py"
```

---

## Task A.4 — Move `targeted` tools

**Files:**
- Create: `app/tools/targeted.py`
- Test: `tests/unit/tools/test_targeted.py`

- [ ] **A.4.1 Write failing test.**

```python
"""Unit tests for targeted tools after migration."""
from __future__ import annotations
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from app.tools import get_tool


def test_get_cell_at_returns_cell(sample_xlsx: Path) -> None:
    """get_cell_at resolves a single A1 address to a Cell."""
    ctx = register_workbook(sample_xlsx)
    cell = get_tool("get_cell_at")(ctx, sheet=ctx.wb.sheetnames[0], address="A1")
    assert cell.address == "A1"


def test_read_relative_offsets(sample_xlsx: Path) -> None:
    """read_relative offsets from an anchor by (dy, dx)."""
    ctx = register_workbook(sample_xlsx)
    cell = get_tool("read_relative")(ctx, sheet=ctx.wb.sheetnames[0],
                                     anchor="A1", dy=0, dx=1)
    assert cell.address == "B1"
```

- [ ] **A.4.2 Run pytest** — failure.

- [ ] **A.4.3 Implement.**

```python
"""Targeted tools — single-cell or single-row reads."""
from __future__ import annotations

from openpyxl.utils import column_index_from_string
from openpyxl.utils.cell import coordinate_from_string

from app.models.workbook import Cell, WorkbookCtx
from app.tools import tool
from app.tools.bulk_read import _cell


@tool("read_row")
def read_row(ctx: WorkbookCtx, sheet: str, row: int,
             col_range: tuple[int, int] | None = None) -> list[Cell]:
    """Read every non-empty cell in `row` within `col_range`, inclusive."""
    ws = ctx.wb[sheet]
    if col_range is None:
        col_range = (1, ws.max_column or 1)
    c0, c1 = col_range
    out: list[Cell] = []
    for c in range(c0, c1 + 1):
        cell = _cell(ws, row, c)
        if cell.value is not None:
            out.append(cell)
    return out


@tool("read_relative")
def read_relative(ctx: WorkbookCtx, sheet: str, anchor: str, dy: int, dx: int) -> Cell:
    """Read the cell at `(anchor + dy rows, anchor + dx cols)`."""
    col_letter, row = coordinate_from_string(anchor)
    col = column_index_from_string(col_letter)
    return _cell(ctx.wb[sheet], row + dy, col + dx)


@tool("get_cell_at")
def get_cell_at(ctx: WorkbookCtx, sheet: str, address: str) -> Cell:
    """Read the cell at an exact A1 address."""
    col_letter, row = coordinate_from_string(address)
    col = column_index_from_string(col_letter)
    return _cell(ctx.wb[sheet], row, col)
```

- [ ] **A.4.4 Re-run pytest** — green.

- [ ] **A.4.5 Commit.**

```bash
git add app/tools/targeted.py tests/unit/tools/test_targeted.py
git commit -m "refactor(tools): move targeted tools to app/tools/targeted.py"
```

---

## Task A.5 — Move `structure` tools

**Files:**
- Create: `app/tools/structure.py`
- Test: `tests/unit/tools/test_structure.py`

- [ ] **A.5.1 Write failing test.**

```python
"""Unit tests for structure tools after migration."""
from __future__ import annotations
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from app.tools import get_tool


def test_get_merged_regions_returns_list(sample_xlsx: Path) -> None:
    """get_merged_regions returns one MergedRegion per merged range."""
    ctx = register_workbook(sample_xlsx)
    regions = get_tool("get_merged_regions")(ctx, sheet=ctx.wb.sheetnames[0])
    assert isinstance(regions, list)


def test_count_non_empty_rows_in_column(sample_xlsx: Path) -> None:
    """count_non_empty_rows_in_column counts populated cells in a column."""
    ctx = register_workbook(sample_xlsx)
    n = get_tool("count_non_empty_rows_in_column")(
        ctx, sheet=ctx.wb.sheetnames[0], column="A",
    )
    assert n >= 0
```

- [ ] **A.5.2 Run pytest** — failure.

- [ ] **A.5.3 Implement.**

```python
"""Structure tools — merged regions and occupancy counts."""
from __future__ import annotations

from openpyxl.utils import column_index_from_string

from app.models.workbook import MergedRegion, WorkbookCtx
from app.tools import tool


@tool("get_merged_regions")
def get_merged_regions(ctx: WorkbookCtx, sheet: str) -> list[MergedRegion]:
    """Return every merged region in `sheet` with its anchor value."""
    ws = ctx.wb[sheet]
    out: list[MergedRegion] = []
    for mr in ws.merged_cells.ranges:
        anchor_value = ws.cell(row=mr.min_row, column=mr.min_col).value
        anchor = ws.cell(row=mr.min_row, column=mr.min_col).coordinate
        out.append(MergedRegion(cell_range=mr.coord, anchor=anchor,
                                anchor_value=anchor_value))
    return out


@tool("count_non_empty_rows_in_column")
def count_non_empty_rows_in_column(ctx: WorkbookCtx, sheet: str, column: str,
                                   row_range: tuple[int, int] | None = None) -> int:
    """Count rows in `column` (inside `row_range`) with a non-empty value."""
    ws = ctx.wb[sheet]
    col_idx = column_index_from_string(column)
    r0, r1 = row_range or (1, ws.max_row or 1)
    return sum(1 for r in range(r0, r1 + 1)
               if ws.cell(row=r, column=col_idx).value is not None)
```

- [ ] **A.5.4 Re-run pytest** — green.

- [ ] **A.5.5 Commit.**

```bash
git add app/tools/structure.py tests/unit/tools/test_structure.py
git commit -m "refactor(tools): move structure tools to app/tools/structure.py"
```

---

## Task A.6 — Move `search` tool

**Files:**
- Create: `app/tools/search.py`
- Test: `tests/unit/tools/test_search.py`

- [ ] **A.6.1 Write failing test.**

```python
"""Unit tests for search tools after migration."""
from __future__ import annotations
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from app.tools import get_tool


def test_find_value_returns_addresses(sample_xlsx: Path) -> None:
    """find_value returns A1 addresses for cells containing the needle."""
    ctx = register_workbook(sample_xlsx)
    hits = get_tool("find_value")(ctx, sheet=ctx.wb.sheetnames[0],
                                  needle="", max_hits=1, case_insensitive=True)
    assert isinstance(hits, list)
```

- [ ] **A.6.2 Run pytest** — failure.

- [ ] **A.6.3 Implement.**

```python
"""Search tools — locate a value within a sheet."""
from __future__ import annotations

from openpyxl.utils import get_column_letter

from app.models.workbook import WorkbookCtx
from app.tools import tool


@tool("find_value")
def find_value(ctx: WorkbookCtx, sheet: str, needle: str,
               max_hits: int = 10, case_insensitive: bool = True) -> list[str]:
    """Return A1 addresses of cells containing `needle` (substring match)."""
    ws = ctx.wb[sheet]
    target = needle.lower() if case_insensitive else needle
    hits: list[str] = []
    for r in range(1, (ws.max_row or 0) + 1):
        for c in range(1, (ws.max_column or 0) + 1):
            v = ws.cell(row=r, column=c).value
            if v is None:
                continue
            s = str(v).lower() if case_insensitive else str(v)
            if target in s:
                hits.append(f"{get_column_letter(c)}{r}")
                if len(hits) >= max_hits:
                    return hits
    return hits
```

- [ ] **A.6.4 Re-run pytest** — green.

- [ ] **A.6.5 Commit.**

```bash
git add app/tools/search.py tests/unit/tools/test_search.py
git commit -m "refactor(tools): move find_value tool to app/tools/search.py"
```

---

## Task A.7 — Rewrite callers to import from `app.tools`

Callers today: `app/services/extraction.py`, `app/services/planner/surveyor.py`, `app/services/agents/*`. After this task they import only `app.tools`.

**Files:**
- Modify: `app/services/extraction.py`
- Modify: `app/services/planner/surveyor.py` (currently has no tool calls, but other planner files may)
- Modify: `app/agents/sheet_classifier/agent.py` (and any other agent referring to TOOL_REGISTRY)
- Modify: `tests/**` — any test importing `app.repositories.workbook_tools._registry`
- Test: `tests/unit/tools/test_registry_callers.py`

- [ ] **A.7.1 Write failing test.**

```python
"""Asserts no production code imports the old workbook_tools registry."""
from __future__ import annotations
import ast
from pathlib import Path
import pytest

_ROOTS = ("app/pipelines", "app/components", "app/agents", "app/inferencing",
          "app/tools", "app/routers", "app/services")


def _imports(path: Path) -> list[str]:
    """Return every imported module path inside `path`."""
    tree = ast.parse(path.read_text())
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
        elif isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
    return mods


@pytest.mark.parametrize("root", _ROOTS)
def test_no_legacy_workbook_tools_imports(root: str) -> None:
    """Every production module imports app.tools, not app.repositories.workbook_tools."""
    for path in Path(root).rglob("*.py"):
        for mod in _imports(path):
            assert "workbook_tools" not in mod, f"{path} still imports {mod}"
```

- [ ] **A.7.2 Run pytest** — failure (orchestrator still imports `app.repositories.workbook_tools.*`).

- [ ] **A.7.3 Implement.**

In `app/services/extraction.py` replace the import block:

```python
# Replace:
# import app.repositories.workbook_tools.bulk_read  # noqa: F401
# import app.repositories.workbook_tools.search  # noqa: F401
# import app.repositories.workbook_tools.structure  # noqa: F401
# import app.repositories.workbook_tools.survey  # noqa: F401
# import app.repositories.workbook_tools.targeted  # noqa: F401
# from app.repositories.workbook_tools._registry import TOOL_REGISTRY

# With:
import app.tools.bulk_read  # noqa: F401  # tool self-registration on import
import app.tools.search  # noqa: F401
import app.tools.structure  # noqa: F401
import app.tools.survey  # noqa: F401
import app.tools.targeted  # noqa: F401
from app.tools import get_tool
```

And rewrite `TOOL_REGISTRY.get("workbook_summary")(ctx)` → `get_tool("workbook_summary")(ctx)`.

Sweep agent files (under `app/agents/<name>/agent.py`) similarly.

- [ ] **A.7.4 Re-run pytest** — green.

- [ ] **A.7.5 Commit.**

```bash
git add app/services/extraction.py app/agents tests/unit/tools/test_registry_callers.py
git commit -m "refactor(tools): switch callers to app.tools (drop legacy registry)"
```

---

## Task A.8 — Checkpoint A

- [ ] **A.8.1 Verify.**

```bash
make test
make eval-smoke
```

Both green. Commit any test-only fixture cleanups if needed; otherwise this is a no-op verification step.

---

# Phase B — Planner sub-components

Goal: each planner sub-module becomes a `Component` subclass so the Pipeline factory can wire it. Pure-function helpers (`_decide_pli_mode`, `_pick_identity_column`, `_classify_single_row`, etc.) move alongside as module-level helpers.

## Task B.1 — `surveyor` Component

**Files:**
- Create: `app/components/planner/__init__.py` (re-export-only)
- Create: `app/components/planner/surveyor.py`
- Test: `tests/unit/components/planner/test_surveyor.py`

- [ ] **B.1.1 Write failing test.**

```python
"""Unit tests for the Surveyor component."""
from __future__ import annotations
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from app.components.planner.surveyor import Surveyor


def test_surveyor_emits_signals(sample_xlsx: Path) -> None:
    """Surveyor.run returns a {'signals': SheetSignals} dict."""
    ctx = register_workbook(sample_xlsx)
    out = Surveyor().run(workbook_ctx=ctx, sheet=ctx.wb.sheetnames[0])
    assert "signals" in out
    assert out["signals"].sheet == ctx.wb.sheetnames[0]
```

- [ ] **B.1.2 Run pytest** — failure.

- [ ] **B.1.3 Implement.**

Move the entire body of `app/services/planner/surveyor.py` verbatim into `app/components/planner/surveyor.py` (replacing the `from app.models.workbook` and similar imports). Then add a Component wrapper:

```python
"""Deterministic single-pass survey of a sheet — emits SheetSignals."""
from __future__ import annotations

from datetime import date, datetime

from haystack import component
from openpyxl.utils import get_column_letter

from app.core.logs import get_logger
from app.models.artifacts import SheetSignals
from app.models.workbook import WorkbookCtx

log = get_logger(__name__)


# … (private helpers _norm, _collect_header_signals, _collect_blank_run_gaps,
#     _collect_date_typed_cols copied verbatim from the old module) …


def survey_sheet(ctx: WorkbookCtx, sheet: str) -> SheetSignals:
    """Survey `sheet` and return a SheetSignals bundle."""
    # body copied verbatim
    ...


@component
class Surveyor:
    """Deterministic sheet surveyor component."""

    @component.output_types(signals=SheetSignals)
    def run(self, workbook_ctx: WorkbookCtx, sheet: str) -> dict:
        """Survey `sheet` and emit SheetSignals."""
        return {"signals": survey_sheet(workbook_ctx, sheet)}
```

- [ ] **B.1.4 Re-run pytest** — green.

- [ ] **B.1.5 Commit.**

```bash
git add app/components/planner/__init__.py app/components/planner/surveyor.py \
        tests/unit/components/planner/test_surveyor.py
git commit -m "refactor(planner): wrap surveyor as a component under app/components/planner"
```

---

## Task B.2 — `row_classifier` Component

**Files:**
- Create: `app/components/planner/row_classifier.py`
- Test: `tests/unit/components/planner/test_row_classifier.py`

- [ ] **B.2.1 Write failing test.**

```python
"""Unit tests for the RowClassifier component."""
from __future__ import annotations
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from app.components.planner.surveyor import survey_sheet
from app.components.planner.row_classifier import RowClassifier


def test_row_classifier_emits_rows(sample_xlsx: Path) -> None:
    """RowClassifier.run returns one RowSpec per sheet row in {'rows': ...}."""
    ctx = register_workbook(sample_xlsx)
    sheet = ctx.wb.sheetnames[0]
    signals = survey_sheet(ctx, sheet)
    out = RowClassifier().run(workbook_ctx=ctx, sheet=sheet, signals=signals,
                              identity_column=None)
    assert "rows" in out
```

- [ ] **B.2.2 Run pytest** — failure.

- [ ] **B.2.3 Implement.**

Move `app/services/planner/row_classifier.py` body to `app/components/planner/row_classifier.py`, then add:

```python
@component
class RowClassifier:
    """Deterministic per-row classifier component."""

    @component.output_types(rows=list)
    def run(self, workbook_ctx: WorkbookCtx, sheet: str, signals: SheetSignals,
            identity_column: str | None, quantity_column_hint: str | None = None) -> dict:
        """Classify every row in `sheet` into a RowSpec."""
        return {"rows": classify_rows(workbook_ctx, sheet, signals,
                                       identity_column=identity_column,
                                       quantity_column_hint=quantity_column_hint)}
```

- [ ] **B.2.4 Re-run pytest** — green.

- [ ] **B.2.5 Commit.**

```bash
git add app/components/planner/row_classifier.py \
        tests/unit/components/planner/test_row_classifier.py
git commit -m "refactor(planner): wrap row_classifier as a component"
```

---

## Task B.3 — `kv_anchor_detector` Component

**Files:**
- Create: `app/components/planner/kv_anchor_detector.py`
- Test: `tests/unit/components/planner/test_kv_anchor_detector.py`

- [ ] **B.3.1 Write failing test.**

```python
"""Unit tests for the KvAnchorDetector component."""
from __future__ import annotations
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from app.components.planner.surveyor import survey_sheet
from app.components.planner.kv_anchor_detector import KvAnchorDetector


def test_kv_anchor_detector_emits_anchors(sample_xlsx: Path) -> None:
    """KvAnchorDetector.run returns {'anchors': list[KVAnchor]}."""
    ctx = register_workbook(sample_xlsx)
    sheet = ctx.wb.sheetnames[0]
    signals = survey_sheet(ctx, sheet)
    out = KvAnchorDetector().run(workbook_ctx=ctx, sheet=sheet, signals=signals)
    assert "anchors" in out
    assert isinstance(out["anchors"], list)
```

- [ ] **B.3.2 Run pytest** — failure.

- [ ] **B.3.3 Implement.**

Copy `detect_kv_anchors` body into the new module, then:

```python
@component
class KvAnchorDetector:
    """Deterministic KV-anchor detector component."""

    @component.output_types(anchors=list)
    def run(self, workbook_ctx: WorkbookCtx, sheet: str, signals: SheetSignals) -> dict:
        """Resolve each KV label hit into a KVAnchor."""
        return {"anchors": detect_kv_anchors(workbook_ctx, sheet, signals)}
```

- [ ] **B.3.4 Re-run pytest** — green.

- [ ] **B.3.5 Commit.**

```bash
git add app/components/planner/kv_anchor_detector.py \
        tests/unit/components/planner/test_kv_anchor_detector.py
git commit -m "refactor(planner): wrap kv_anchor_detector as a component"
```

---

## Task B.4 — `stage_band_detector` Component

**Files:**
- Create: `app/components/planner/stage_band_detector.py`
- Test: `tests/unit/components/planner/test_stage_band_detector.py`

- [ ] **B.4.1 Write failing test.**

```python
"""Unit tests for the StageBandDetector component."""
from __future__ import annotations
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from app.components.planner.surveyor import survey_sheet
from app.components.planner.stage_band_detector import StageBandDetector


def test_stage_band_detector_emits_bands(sample_xlsx: Path) -> None:
    """StageBandDetector.run returns {'bands': list[StageBandSpec]}."""
    ctx = register_workbook(sample_xlsx)
    sheet = ctx.wb.sheetnames[0]
    signals = survey_sheet(ctx, sheet)
    out = StageBandDetector().run(workbook_ctx=ctx, sheet=sheet, signals=signals)
    assert "bands" in out
```

- [ ] **B.4.2 Run pytest** — failure.

- [ ] **B.4.3 Implement.**

Move all helpers + `detect_stage_bands` verbatim, then:

```python
@component
class StageBandDetector:
    """Deterministic stage-band detector component."""

    @component.output_types(bands=list)
    def run(self, workbook_ctx: WorkbookCtx, sheet: str, signals: SheetSignals) -> dict:
        """Detect all stage-band rectangles in `sheet`."""
        return {"bands": detect_stage_bands(workbook_ctx, sheet, signals)}
```

- [ ] **B.4.4 Re-run pytest** — green.

- [ ] **B.4.5 Commit.**

```bash
git add app/components/planner/stage_band_detector.py \
        tests/unit/components/planner/test_stage_band_detector.py
git commit -m "refactor(planner): wrap stage_band_detector as a component"
```

---

## Task B.5 — `block_segmenter` Component

**Files:**
- Create: `app/components/planner/block_segmenter.py`
- Test: `tests/unit/components/planner/test_block_segmenter.py`

- [ ] **B.5.1 Write failing test.**

```python
"""Unit tests for the BlockSegmenter component."""
from __future__ import annotations
from app.components.planner.block_segmenter import BlockSegmenter


def test_block_segmenter_returns_empty_for_no_anchors() -> None:
    """BlockSegmenter.run returns {'blocks': []} when no anchor rows exist."""
    out = BlockSegmenter().run(rows=[], kv_anchors=[], blank_run_gaps=[],
                                stage_bands=[])
    assert out == {"blocks": []}
```

- [ ] **B.5.2 Run pytest** — failure.

- [ ] **B.5.3 Implement.**

Copy `segment_blocks` verbatim, then:

```python
@component
class BlockSegmenter:
    """Deterministic PLI-block segmenter component."""

    @component.output_types(blocks=list)
    def run(self, rows: list, kv_anchors: list,
            blank_run_gaps: list, stage_bands: list | None = None) -> dict:
        """Segment ANCHOR rows into PliBlocks."""
        return {"blocks": segment_blocks(rows, kv_anchors,
                                          blank_run_gaps, stage_bands)}
```

- [ ] **B.5.4 Re-run pytest** — green.

- [ ] **B.5.5 Commit.**

```bash
git add app/components/planner/block_segmenter.py \
        tests/unit/components/planner/test_block_segmenter.py
git commit -m "refactor(planner): wrap block_segmenter as a component"
```

---

## Task B.6 — Move `SheetRowPlanner` to `app/components/planner/plan.py`

**Files:**
- Create: `app/components/planner/plan.py`
- Modify: `app/services/extraction.py` — switch imports
- Test: `tests/unit/components/planner/test_plan.py`

- [ ] **B.6.1 Write failing test.**

```python
"""Unit tests for the migrated SheetRowPlanner."""
from __future__ import annotations
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from app.components.planner.plan import SheetRowPlanner


def test_planner_emits_plan(sample_xlsx: Path) -> None:
    """SheetRowPlanner.run returns {'plan': SheetPlan}."""
    ctx = register_workbook(sample_xlsx)
    sheet = ctx.wb.sheetnames[0]
    out = SheetRowPlanner().run(workbook_ctx=ctx, sheet=sheet)
    assert "plan" in out
    assert out["plan"].sheet == sheet
```

- [ ] **B.6.2 Run pytest** — failure.

- [ ] **B.6.3 Implement.**

Move the entire body of `app/services/planner/plan.py` to `app/components/planner/plan.py`, updating internal imports:

```python
from app.components.planner.block_segmenter import segment_blocks
from app.components.planner.kv_anchor_detector import detect_kv_anchors
from app.components.planner.row_classifier import classify_rows
from app.components.planner.stage_band_detector import detect_stage_bands
from app.components.planner.surveyor import survey_sheet
```

The `@component class SheetRowPlanner` declaration carries over unchanged (its `run()` already returns `{"plan": SheetPlan}`).

Then update `app/services/extraction.py`:

```python
# Replace:
# from app.services.planner.plan import SheetRowPlanner
# from app.services.planner.surveyor import survey_sheet

# With:
from app.components.planner.plan import SheetRowPlanner
from app.components.planner.surveyor import survey_sheet
```

- [ ] **B.6.4 Re-run pytest** — green.

- [ ] **B.6.5 Commit.**

```bash
git add app/components/planner/plan.py app/services/extraction.py \
        tests/unit/components/planner/test_plan.py
git commit -m "refactor(planner): move SheetRowPlanner to app/components/planner"
```

---

## Task B.7 — Checkpoint B

- [ ] **B.7.1 Verify.**

```bash
make test
make eval-smoke
```

Both green.

---

# Phase C — Existing validators

`coverage_verifier`, `field_dropout_verifier`, `header_match_verifier`, `source_cell_verifier` already carry `@component`. `plan_invariants` and `plan_statistics` are plain functions and gain a Component wrapper here.

## Task C.1 — `plan_invariants` → `app/components/validators/plan_invariants.py`

**Files:**
- Create: `app/components/validators/__init__.py` (re-export-only)
- Create: `app/components/validators/plan_invariants.py`
- Modify: `app/services/extraction.py` — switch import
- Test: `tests/unit/components/validators/test_plan_invariants.py`

- [ ] **C.1.1 Write failing test.**

```python
"""Unit tests for the PlanInvariantsValidator component."""
from __future__ import annotations
from app.components.validators.plan_invariants import (
    PlanInvariantsValidator, validate_invariants,
)
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.models.artifacts import RowSpec, SheetPlan


def test_validator_run_returns_findings() -> None:
    """PlanInvariantsValidator.run returns {'findings': list[ValidationFinding]}."""
    plan = SheetPlan(sheet="s", pli_mode=PliMode.ROW_PER_PLI,
                     identity_column="A", header_rows=[1],
                     rows=[RowSpec(idx=1, role=RowRole.HEADER)],
                     pli_blocks=[], kv_anchors=[],
                     header_labels=[], stage_bands=[],
                     stage_scope=StageScope.SHEET_LEVEL, confidence=0.9)
    out = PlanInvariantsValidator().run(plan=plan)
    assert "findings" in out
```

- [ ] **C.1.2 Run pytest** — failure.

- [ ] **C.1.3 Implement.**

Copy the entire body of `app/services/validation/plan_invariants.py` (including `validate_invariants` and helpers) to the new location, then append:

```python
@component
class PlanInvariantsValidator:
    """Tier-1 plan invariants validator component."""

    @component.output_types(findings=list)
    def run(self, plan: SheetPlan) -> dict:
        """Run all Tier-1 invariant checks against `plan`."""
        return {"findings": validate_invariants(plan)}
```

Update orchestrator import:

```python
from app.components.validators.plan_invariants import validate_invariants
```

- [ ] **C.1.4 Re-run pytest** — green.

- [ ] **C.1.5 Commit.**

```bash
git add app/components/validators/__init__.py \
        app/components/validators/plan_invariants.py \
        app/services/extraction.py \
        tests/unit/components/validators/test_plan_invariants.py
git commit -m "refactor(validators): move plan_invariants to app/components/validators"
```

---

## Task C.2 — `plan_statistics` → `app/components/validators/plan_statistics.py`

**Files:**
- Create: `app/components/validators/plan_statistics.py`
- Modify: `app/services/extraction.py`
- Test: `tests/unit/components/validators/test_plan_statistics.py`

- [ ] **C.2.1 Write failing test.**

```python
"""Unit tests for the PlanStatisticsValidator component."""
from __future__ import annotations
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from app.components.planner.plan import SheetRowPlanner
from app.components.validators.plan_statistics import PlanStatisticsValidator


def test_statistics_validator_runs(sample_xlsx: Path) -> None:
    """PlanStatisticsValidator.run returns {'findings': list[ValidationFinding]}."""
    ctx = register_workbook(sample_xlsx)
    plan = SheetRowPlanner().run(workbook_ctx=ctx,
                                  sheet=ctx.wb.sheetnames[0])["plan"]
    out = PlanStatisticsValidator().run(workbook_ctx=ctx, plan=plan)
    assert "findings" in out
```

- [ ] **C.2.2 Run pytest** — failure.

- [ ] **C.2.3 Implement.**

Move source verbatim, then:

```python
@component
class PlanStatisticsValidator:
    """Tier-2 plan statistical-sanity validator component."""

    @component.output_types(findings=list)
    def run(self, workbook_ctx: WorkbookCtx, plan: SheetPlan) -> dict:
        """Run all Tier-2 statistical checks against `plan`."""
        return {"findings": validate_statistics(workbook_ctx, plan)}
```

- [ ] **C.2.4 Re-run pytest** — green.

- [ ] **C.2.5 Commit.**

```bash
git add app/components/validators/plan_statistics.py \
        app/services/extraction.py \
        tests/unit/components/validators/test_plan_statistics.py
git commit -m "refactor(validators): move plan_statistics to app/components/validators"
```

---

## Task C.3 — `coverage_verifier`

**Files:**
- Create: `app/components/validators/coverage_verifier.py`
- Modify: `app/services/extraction.py`
- Test: keep `tests/unit/validation/test_coverage.py` content; if it imports the old path, update it.

- [ ] **C.3.1 Write failing test (move-existing).**

Move the existing test file to `tests/unit/components/validators/test_coverage_verifier.py` and switch its import to `from app.components.validators.coverage_verifier import CoverageVerifier`.

- [ ] **C.3.2 Run pytest** — failure (path doesn't exist).

- [ ] **C.3.3 Implement.**

Copy `app/services/validation/coverage_verifier.py` verbatim into the new path. No body changes needed; it already uses `@component`.

Update orchestrator:

```python
from app.components.validators.coverage_verifier import CoverageVerifier
```

- [ ] **C.3.4 Re-run pytest** — green.

- [ ] **C.3.5 Commit.**

```bash
git add app/components/validators/coverage_verifier.py \
        app/services/extraction.py \
        tests/unit/components/validators/test_coverage_verifier.py
git commit -m "refactor(validators): move coverage_verifier to app/components/validators"
```

---

## Task C.4 — `field_dropout_verifier`

**Files:**
- Create: `app/components/validators/field_dropout_verifier.py`
- Modify: `app/services/extraction.py`
- Test: `tests/unit/components/validators/test_field_dropout_verifier.py`

- [ ] **C.4.1 Write failing test (move-existing).**

Move the existing test, switch import.

- [ ] **C.4.2 Run pytest** — failure.

- [ ] **C.4.3 Implement.**

Copy verbatim; switch orchestrator import.

- [ ] **C.4.4 Re-run pytest** — green.

- [ ] **C.4.5 Commit.**

```bash
git commit -m "refactor(validators): move field_dropout_verifier to app/components/validators"
```

---

## Task C.5 — `header_match_verifier`

**Files:**
- Create: `app/components/validators/header_match_verifier.py`
- Modify: `app/services/extraction.py`
- Test: `tests/unit/components/validators/test_header_match_verifier.py`

- [ ] **C.5.1 Write failing test (move-existing).** Move + switch import.

- [ ] **C.5.2 Run pytest** — failure.

- [ ] **C.5.3 Implement.** Copy verbatim; switch orchestrator import.

- [ ] **C.5.4 Re-run pytest** — green.

- [ ] **C.5.5 Commit.**

```bash
git commit -m "refactor(validators): move header_match_verifier to app/components/validators"
```

---

## Task C.6 — `source_cell_verifier`

**Files:**
- Create: `app/components/validators/source_cell_verifier.py`
- Modify: `app/services/extraction.py`
- Test: `tests/unit/components/validators/test_source_cell_verifier.py`

- [ ] **C.6.1 Write failing test (move-existing).** Move + switch import.

- [ ] **C.6.2 Run pytest** — failure.

- [ ] **C.6.3 Implement.** Copy verbatim; switch orchestrator import.

- [ ] **C.6.4 Re-run pytest** — green.

- [ ] **C.6.5 Commit.**

```bash
git commit -m "refactor(validators): move source_cell_verifier to app/components/validators"
```

---

## Task C.7 — Checkpoint C

- [ ] **C.7.1 Verify.**

```bash
make test
make eval-smoke
```

Both green.

---

# Phase D — New between-agents validators

Three new Components close the multi-point-failure gap called out in spec §5. Each runs immediately after the LLM-driven mutation it audits.

## Task D.1 — `post_review_plan` validator (failing test)

**Goal:** after PlanReviewer applies `row_corrections`, re-run `validate_invariants`. If the corrections introduced an error, attach a Warning so the orchestrator falls back to the pre-review plan.

**Files:**
- Test: `tests/unit/components/validators/test_post_review_plan.py`

- [ ] **D.1.1 Write failing test.**

```python
"""Unit tests for the PostReviewPlanValidator between-agents validator."""
from __future__ import annotations
from app.components.validators.post_review_plan import PostReviewPlanValidator
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import HeaderLabel, RowSpec, SheetPlan


def _plan(rows: list[RowSpec]) -> SheetPlan:
    """Build a minimal ROW_PER_PLI SheetPlan for testing."""
    return SheetPlan(sheet="s", pli_mode=PliMode.ROW_PER_PLI, identity_column="A",
                     header_rows=[1], rows=rows, pli_blocks=[], kv_anchors=[],
                     header_labels=[HeaderLabel(raw="io", col="A", row=1)],
                     stage_bands=[], stage_scope=StageScope.SHEET_LEVEL,
                     confidence=0.9)


def test_post_review_passes_on_clean_plan() -> None:
    """When corrections preserve invariants, findings are empty."""
    rows = [RowSpec(idx=1, role=RowRole.HEADER),
            RowSpec(idx=2, role=RowRole.ANCHOR, group_id=0)]
    out = PostReviewPlanValidator().run(plan=_plan(rows))
    assert out["findings"] == []


def test_post_review_emits_finding_on_broken_invariant() -> None:
    """A CHILD with no anchor_idx (introduced by the reviewer) produces an ERROR finding."""
    rows = [RowSpec(idx=1, role=RowRole.HEADER),
            RowSpec(idx=2, role=RowRole.CHILD)]  # missing anchor_idx
    out = PostReviewPlanValidator().run(plan=_plan(rows))
    assert any(f.severity == ValidationSeverity.ERROR for f in out["findings"])
```

- [ ] **D.1.2 Run pytest** — failure: `ModuleNotFoundError: app.components.validators.post_review_plan`.

---

## Task D.2 — `post_review_plan` Component impl

**Files:**
- Create: `app/components/validators/post_review_plan.py`

- [ ] **D.2.1 Implement.**

```python
"""Between-agents validator — re-checks invariants after PlanReviewer corrections."""
from __future__ import annotations

from haystack import component

from app.components.validators.plan_invariants import validate_invariants
from app.core.logs import get_logger
from app.core.telemetry import validator_findings_total
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import SheetPlan, ValidationFinding

log = get_logger(__name__)


@component
class PostReviewPlanValidator:
    """Re-runs Tier-1 invariants after PlanReviewer mutates `plan.rows`."""

    @component.output_types(findings=list)
    def run(self, plan: SheetPlan) -> dict:
        """Return any invariant findings introduced by row_corrections."""
        findings: list[ValidationFinding] = validate_invariants(plan)
        for f in findings:
            if f.severity == ValidationSeverity.ERROR:
                log.warning("post_review_invariant_break",
                            check=f.check, message=f.message)
                validator_findings_total.add(
                    1, {"check": f"post_review.{f.check}", "severity": "error"},
                )
        return {"findings": findings}
```

- [ ] **D.2.2 Re-run pytest** — green.

- [ ] **D.2.3 Commit.**

```bash
git add app/components/validators/post_review_plan.py \
        tests/unit/components/validators/test_post_review_plan.py
git commit -m "feat(validators): add PostReviewPlanValidator (post-PlanReviewer gate)"
```

---

## Task D.3 — `post_namer_canonical` validator (failing test)

**Goal:** after FieldNamer, verify every detected label was either mapped to a known canonical or explicitly set to `"ignore"`. No silent drops.

**Files:**
- Test: `tests/unit/components/validators/test_post_namer_canonical.py`

- [ ] **D.3.1 Write failing test.**

```python
"""Unit tests for the PostNamerCanonicalValidator between-agents validator."""
from __future__ import annotations
from app.components.validators.post_namer_canonical import PostNamerCanonicalValidator
from app.enums.pli_mode import PliMode
from app.enums.stage_scope import StageScope
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import CanonicalNameMap, HeaderLabel, SheetPlan


def _plan(labels: list[HeaderLabel]) -> SheetPlan:
    """Build a minimal ROW_PER_PLI SheetPlan with `labels`."""
    return SheetPlan(sheet="s", pli_mode=PliMode.ROW_PER_PLI, identity_column="A",
                     header_rows=[1], rows=[], pli_blocks=[], kv_anchors=[],
                     header_labels=labels, stage_bands=[],
                     stage_scope=StageScope.SHEET_LEVEL, confidence=0.9)


def test_post_namer_clean() -> None:
    """Every detected label is mapped; findings empty."""
    plan = _plan([HeaderLabel(raw="IO No", col="A", row=1)])
    name_map = CanonicalNameMap(
        field_labels={"IO No": "io_number"},
        stage_names={}, stage_subfield_labels={},
        field_confidence={}, stage_confidence={},
    )
    out = PostNamerCanonicalValidator().run(plan=plan, name_map=name_map)
    assert out["findings"] == []


def test_post_namer_silent_drop() -> None:
    """A detected label missing from the name_map produces a WARN finding."""
    plan = _plan([HeaderLabel(raw="Mystery Field", col="B", row=1)])
    name_map = CanonicalNameMap(
        field_labels={}, stage_names={}, stage_subfield_labels={},
        field_confidence={}, stage_confidence={},
    )
    out = PostNamerCanonicalValidator().run(plan=plan, name_map=name_map)
    assert any(f.severity == ValidationSeverity.WARN
               and "Mystery Field" in f.message
               for f in out["findings"])
```

- [ ] **D.3.2 Run pytest** — failure.

---

## Task D.4 — `post_namer_canonical` Component impl

**Files:**
- Create: `app/components/validators/post_namer_canonical.py`

- [ ] **D.4.1 Implement.**

```python
"""Between-agents validator — confirms every detected label was named or ignored."""
from __future__ import annotations

from haystack import component

from app.core.logs import get_logger
from app.core.telemetry import validator_findings_total
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import (
    CanonicalNameMap, KVAnchor, SheetPlan, ValidationFinding,
)

log = get_logger(__name__)


def _detected_raw_labels(plan: SheetPlan) -> set[str]:
    """Collect every raw label the planner found across all identity channels."""
    raws: set[str] = set()
    raws.update(hl.raw for hl in plan.header_labels)
    raws.update(kv.field for kv in plan.kv_anchors)
    for blk in plan.pli_blocks:
        raws.update(kv.field for kv in blk.identity)
    return raws


def _detected_stage_names(plan: SheetPlan) -> set[str]:
    """Collect every raw stage name the planner emitted."""
    names: set[str] = set()
    for band in plan.stage_bands:
        names.update(sc.name for sc in band.stage_columns)
    for blk in plan.pli_blocks:
        for band in blk.stage_bands:
            names.update(sc.name for sc in band.stage_columns)
    return names


@component
class PostNamerCanonicalValidator:
    """Confirms every planner-detected label has a name_map entry."""

    @component.output_types(findings=list)
    def run(self, plan: SheetPlan, name_map: CanonicalNameMap) -> dict:
        """Emit a WARN for every silently dropped label or stage name."""
        findings: list[ValidationFinding] = []
        for raw in _detected_raw_labels(plan):
            if raw not in name_map.field_labels:
                findings.append(ValidationFinding(
                    check="post_namer_label_silently_dropped",
                    severity=ValidationSeverity.WARN,
                    message=f"detected label {raw!r} not in name_map.field_labels",
                ))
                validator_findings_total.add(
                    1, {"check": "post_namer.label_drop", "severity": "warn"},
                )
        for raw in _detected_stage_names(plan):
            if raw not in name_map.stage_names:
                findings.append(ValidationFinding(
                    check="post_namer_stage_silently_dropped",
                    severity=ValidationSeverity.WARN,
                    message=f"detected stage {raw!r} not in name_map.stage_names",
                ))
                validator_findings_total.add(
                    1, {"check": "post_namer.stage_drop", "severity": "warn"},
                )
        if findings:
            log.warning("post_namer_silent_drops", count=len(findings))
        return {"findings": findings}
```

- [ ] **D.4.2 Re-run pytest** — green.

- [ ] **D.4.3 Commit.**

```bash
git add app/components/validators/post_namer_canonical.py \
        tests/unit/components/validators/test_post_namer_canonical.py
git commit -m "feat(validators): add PostNamerCanonicalValidator (post-FieldNamer gate)"
```

---

## Task D.5 — `pre_apply_readiness` validator (failing test)

**Goal:** before `apply_plan`, verify the plan's identity channel matches `pli_mode` and stage_bands are present where required.

**Files:**
- Test: `tests/unit/components/validators/test_pre_apply_readiness.py`

- [ ] **D.5.1 Write failing test.**

```python
"""Unit tests for the PreApplyReadinessValidator gate."""
from __future__ import annotations
import pytest
from app.components.validators.pre_apply_readiness import PreApplyReadinessValidator
from app.enums.pli_mode import PliMode
from app.enums.stage_scope import StageScope
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import KVAnchor, SheetPlan


def _plan(mode: PliMode, **overrides) -> SheetPlan:
    """Build a minimal SheetPlan for the chosen pli_mode."""
    base = dict(sheet="s", pli_mode=mode, identity_column=None,
                header_rows=[], rows=[], pli_blocks=[], kv_anchors=[],
                header_labels=[], stage_bands=[],
                stage_scope=StageScope.SHEET_LEVEL, confidence=0.9)
    base.update(overrides)
    return SheetPlan(**base)


def test_sheet_is_pli_requires_kv_anchors() -> None:
    """SHEET_IS_PLI with no kv_anchors emits an ERROR finding."""
    plan = _plan(PliMode.SHEET_IS_PLI)
    out = PreApplyReadinessValidator().run(plan=plan)
    assert any(f.severity == ValidationSeverity.ERROR
               and "kv_anchors" in f.message for f in out["findings"])


def test_sheet_is_pli_with_kv_anchors_passes() -> None:
    """SHEET_IS_PLI with at least one KVAnchor produces no readiness errors."""
    plan = _plan(PliMode.SHEET_IS_PLI,
                 kv_anchors=[KVAnchor(label_cell="A1", value_cell="B1", field="io")])
    out = PreApplyReadinessValidator().run(plan=plan)
    assert all(f.severity != ValidationSeverity.ERROR for f in out["findings"])
```

- [ ] **D.5.2 Run pytest** — failure.

---

## Task D.6 — `pre_apply_readiness` Component impl

**Files:**
- Create: `app/components/validators/pre_apply_readiness.py`

- [ ] **D.6.1 Implement.**

```python
"""Between-agents validator — confirms a plan is ready to feed apply_plan."""
from __future__ import annotations

from haystack import component

from app.core.logs import get_logger
from app.core.telemetry import validator_findings_total
from app.enums.pli_mode import PliMode
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import SheetPlan, ValidationFinding

log = get_logger(__name__)


_REQUIRED_CHANNEL = {
    PliMode.ROW_PER_PLI: ("header_labels",
                          lambda p: bool(p.header_labels)),
    PliMode.SHEET_IS_PLI: ("kv_anchors",
                           lambda p: bool(p.kv_anchors)),
    PliMode.SECTION_PER_PLI: ("pli_blocks",
                              lambda p: bool(p.pli_blocks)
                              and all(b.identity for b in p.pli_blocks)),
}


def _check_identity_channel(plan: SheetPlan) -> list[ValidationFinding]:
    """Verify the identity channel required for `plan.pli_mode` is populated."""
    name, predicate = _REQUIRED_CHANNEL[plan.pli_mode]
    if predicate(plan):
        return []
    return [ValidationFinding(
        check="pre_apply_identity_channel",
        severity=ValidationSeverity.ERROR,
        message=(f"pli_mode={plan.pli_mode.value} requires populated "
                 f"{name}; refusing to call apply_plan"),
    )]


def _check_stage_bands(plan: SheetPlan) -> list[ValidationFinding]:
    """Warn when no stage bands are reachable — apply_plan will emit zero stages."""
    has_sheet_bands = bool(plan.stage_bands)
    has_block_bands = any(b.stage_bands for b in plan.pli_blocks)
    if not (has_sheet_bands or has_block_bands):
        return [ValidationFinding(
            check="pre_apply_stage_bands_missing",
            severity=ValidationSeverity.WARN,
            message="plan has no stage_bands; PLIs will have empty stages",
        )]
    return []


@component
class PreApplyReadinessValidator:
    """Final readiness gate run immediately before apply_plan."""

    @component.output_types(findings=list)
    def run(self, plan: SheetPlan) -> dict:
        """Emit findings when the plan's identity channel or stage bands look wrong."""
        findings: list[ValidationFinding] = []
        findings.extend(_check_identity_channel(plan))
        findings.extend(_check_stage_bands(plan))
        for f in findings:
            validator_findings_total.add(
                1, {"check": f.check, "severity": f.severity.value},
            )
        if findings:
            log.warning("pre_apply_readiness", count=len(findings),
                        checks=[f.check for f in findings])
        return {"findings": findings}
```

- [ ] **D.6.2 Re-run pytest** — green.

- [ ] **D.6.3 Commit.**

```bash
git add app/components/validators/pre_apply_readiness.py \
        tests/unit/components/validators/test_pre_apply_readiness.py
git commit -m "feat(validators): add PreApplyReadinessValidator (pre-apply_plan gate)"
```

---

## Task D.7 — Checkpoint D

- [ ] **D.7.1 Verify.**

```bash
make test
make eval-smoke
```

Both green. The new validators are wired into the Pipeline factory in Phase F.

---

# Phase E — Applier + Reconciler

## Task E.1 — Move `apply_plan` → `app/components/applier.py`

**Files:**
- Create: `app/components/applier.py`
- Modify: `app/services/extraction.py`
- Test: `tests/unit/components/test_applier.py`

- [ ] **E.1.1 Write failing test.**

```python
"""Unit tests for the Applier component."""
from __future__ import annotations
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from app.components.applier import Applier, apply_plan
from app.components.planner.plan import SheetRowPlanner
from app.models.artifacts import CanonicalNameMap


def _empty_map() -> CanonicalNameMap:
    return CanonicalNameMap(field_labels={}, stage_names={},
                             stage_subfield_labels={}, field_confidence={},
                             stage_confidence={})


def test_applier_runs(sample_xlsx: Path) -> None:
    """Applier.run dispatches on pli_mode and returns {'plis': list[PLI]}."""
    ctx = register_workbook(sample_xlsx)
    plan = SheetRowPlanner().run(workbook_ctx=ctx,
                                  sheet=ctx.wb.sheetnames[0])["plan"]
    out = Applier().run(workbook_ctx=ctx, plan=plan, name_map=_empty_map())
    assert "plis" in out
    assert isinstance(out["plis"], list)


def test_apply_plan_function_unchanged(sample_xlsx: Path) -> None:
    """The module-level apply_plan function still returns list[PLI]."""
    ctx = register_workbook(sample_xlsx)
    plan = SheetRowPlanner().run(workbook_ctx=ctx,
                                  sheet=ctx.wb.sheetnames[0])["plan"]
    plis = apply_plan(ctx, plan, _empty_map())
    assert isinstance(plis, list)
```

- [ ] **E.1.2 Run pytest** — failure.

- [ ] **E.1.3 Implement.**

Move the entire body of `app/services/applier/apply_plan.py` to `app/components/applier.py`. Append the Component wrapper:

```python
@component
class Applier:
    """Deterministic plan executor — wraps apply_plan as a Haystack Component."""

    @component.output_types(plis=list)
    def run(self, workbook_ctx: WorkbookCtx, plan: SheetPlan,
            name_map: CanonicalNameMap) -> dict:
        """Dispatch on pli_mode and emit list[PLI]."""
        return {"plis": apply_plan(workbook_ctx, plan, name_map)}
```

Update orchestrator:

```python
from app.components.applier import apply_plan
```

- [ ] **E.1.4 Re-run pytest** — green.

- [ ] **E.1.5 Commit.**

```bash
git add app/components/applier.py app/services/extraction.py \
        tests/unit/components/test_applier.py
git commit -m "refactor(applier): move apply_plan to app/components/applier.py"
```

---

## Task E.2 — Move `reconcile` → `app/components/reconciler.py`

**Files:**
- Create: `app/components/reconciler.py`
- Modify: `app/services/extraction.py`
- Test: `tests/unit/components/test_reconciler.py`

- [ ] **E.2.1 Write failing test.**

```python
"""Unit tests for the Reconciler component."""
from __future__ import annotations
from app.components.reconciler import Reconciler, reconcile
from app.models.artifacts import ValidationFindings
from app.models.extraction import ExtractionResult


def test_reconciler_passes_workflow_through() -> None:
    """Reconciler.run returns {'result': ExtractionResult} with merged warnings."""
    workflow = ExtractionResult(plis=[], source_file="x.xlsx")
    findings = ValidationFindings(findings=[])
    out = Reconciler().run(workflow=workflow, validation=findings)
    assert "result" in out
    assert isinstance(out["result"], ExtractionResult)


def test_reconcile_function_unchanged() -> None:
    """The module-level reconcile function still returns ExtractionResult."""
    workflow = ExtractionResult(plis=[], source_file="x.xlsx")
    findings = ValidationFindings(findings=[])
    out = reconcile(workflow_out=workflow, validation_out=findings)
    assert isinstance(out, ExtractionResult)
```

- [ ] **E.2.2 Run pytest** — failure.

- [ ] **E.2.3 Implement.**

Move `app/services/reconciler.py` body verbatim. Append:

```python
@component
class Reconciler:
    """Merges workflow output and validation findings into a final ExtractionResult."""

    @component.output_types(result=ExtractionResult)
    def run(self, workflow: ExtractionResult,
            validation: ValidationFindings) -> dict:
        """Run V1 lenient reconciliation."""
        return {"result": reconcile(workflow_out=workflow,
                                     validation_out=validation)}
```

Update orchestrator:

```python
from app.components.reconciler import reconcile
```

- [ ] **E.2.4 Re-run pytest** — green.

- [ ] **E.2.5 Commit.**

```bash
git add app/components/reconciler.py app/services/extraction.py \
        tests/unit/components/test_reconciler.py
git commit -m "refactor(reconciler): move reconcile to app/components/reconciler.py"
```

---

## Task E.3 — Static-import-guard for applier

The legacy guard test at `tests/unit/applier/test_apply_plan_no_llm_imports.py` checks `app/services/applier/apply_plan.py`. Update it to point at the new location.

**Files:**
- Modify: `tests/unit/applier/test_apply_plan_no_llm_imports.py` → move to `tests/unit/components/test_applier_no_llm_imports.py`

- [ ] **E.3.1 Update the guard test.**

```python
"""Static AST scan: apply_plan must never import an LLM-related module."""
from __future__ import annotations
import ast
from pathlib import Path

_BANNED = (
    "app.services.llm_provider",
    "app.inferencing.anthropic",
    "app.inferencing._base",
    "app.agents",
    "anthropic",
)


def test_applier_module_has_no_llm_imports() -> None:
    """AST-walk app/components/applier.py and assert no LLM imports."""
    tree = ast.parse(Path("app/components/applier.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not any(node.module.startswith(b) for b in _BANNED), node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not any(alias.name.startswith(b) for b in _BANNED), alias.name
```

- [ ] **E.3.2 Run pytest** — green.

- [ ] **E.3.3 Commit.**

```bash
git add tests/unit/components/test_applier_no_llm_imports.py
git rm tests/unit/applier/test_apply_plan_no_llm_imports.py
git commit -m "test(applier): move zero-LLM static guard to components path"
```

---

## Task E.4 — Checkpoint E

- [ ] **E.4.1 Verify.**

```bash
make test
make eval-smoke
```

Both green.

---

# Phase F — Haystack Pipeline factory

This phase replaces `app/services/extraction.py` with a declarative `Pipeline` built in `app/pipelines/extract.py`.

## Task F.1 — Add `HAYSTACK_CONTENT_TRACING_ENABLED=true` to dev/test config

**Files:**
- Modify: `.env`
- Modify: `.env.development`
- Modify: `pytest` fixture in `tests/conftest.py` (or wherever env is set for tests)
- Modify: `docs/SPEC.md` operational notes (production must set the same env var)

- [ ] **F.1.1 Implement.**

Add `HAYSTACK_CONTENT_TRACING_ENABLED=true` to dev + test env. Document in SPEC.md operational notes that production deployments must also set it for the per-component span attributes to flow into SigNoz.

- [ ] **F.1.2 Verify.**

```bash
HAYSTACK_CONTENT_TRACING_ENABLED=true python -c "import os; print(os.environ['HAYSTACK_CONTENT_TRACING_ENABLED'])"
```

- [ ] **F.1.3 Commit.**

```bash
git add .env .env.development tests/conftest.py docs/SPEC.md
git commit -m "chore(observability): enable HAYSTACK_CONTENT_TRACING_ENABLED in dev/test"
```

---

## Task F.2 — Failing wiring test for `make_extract_pipeline`

**Files:**
- Test: `tests/integration/test_haystack_pipeline_wiring.py`

- [ ] **F.2.1 Write failing test.**

```python
"""Integration test: make_extract_pipeline wires every required component."""
from __future__ import annotations
from app.pipelines.extract import make_extract_pipeline
from app.pipelines.tuning import PipelineTuning
from tests.fakes import FakeLLM


def test_pipeline_factory_returns_pipeline() -> None:
    """make_extract_pipeline returns a Haystack Pipeline."""
    pipeline = make_extract_pipeline(llm=FakeLLM(), tuning=PipelineTuning())
    assert pipeline is not None


def test_pipeline_topology() -> None:
    """The pipeline declares the expected components and edges."""
    pipeline = make_extract_pipeline(llm=FakeLLM(), tuning=PipelineTuning())
    names = {n for n, _ in pipeline.walk()}
    expected = {
        "sheet_classifier", "planner", "plan_invariants", "plan_statistics",
        "layout_hinter", "plan_reviewer", "post_review_plan",
        "field_namer", "post_namer_canonical", "pre_apply_readiness",
        "applier", "source_cell_verifier", "header_match_verifier",
        "coverage_verifier", "field_dropout_verifier", "reconciler",
    }
    assert expected.issubset(names)
```

- [ ] **F.2.2 Run pytest** — failure (`app.pipelines.extract` doesn't exist yet).

---

## Task F.3 — `app/pipelines/extract.py` — `make_extract_pipeline`

**Files:**
- Create: `app/pipelines/extract.py`

- [ ] **F.3.1 Implement.**

```python
"""Haystack Pipeline factory for the TNA extraction workflow.

Wires the seven primitives declared in spec §3 into the per-sheet topology:
SheetClassifier → SheetRowPlanner → tier-1/2 validators → (conditional)
LayoutHinter + PlanReviewer → post_review_plan → FieldNamer →
post_namer_canonical → pre_apply_readiness → Applier → tier-3 validators →
Reconciler. The per-sheet loop is driven by the wrapping `extract()` function;
the pipeline itself is built once per request and run per relevant sheet.
"""
from __future__ import annotations

from haystack import Pipeline

from app.agents.field_namer import FieldNamerAgent
from app.agents.layout_hinter import LayoutHinterAgent
from app.agents.plan_reviewer import PlanReviewerAgent
from app.agents.sheet_classifier import SheetClassifierAgent
from app.components.applier import Applier
from app.components.planner.plan import SheetRowPlanner
from app.components.reconciler import Reconciler
from app.components.validators.coverage_verifier import CoverageVerifier
from app.components.validators.field_dropout_verifier import FieldDropoutVerifier
from app.components.validators.header_match_verifier import HeaderMatchVerifier
from app.components.validators.plan_invariants import PlanInvariantsValidator
from app.components.validators.plan_statistics import PlanStatisticsValidator
from app.components.validators.post_namer_canonical import PostNamerCanonicalValidator
from app.components.validators.post_review_plan import PostReviewPlanValidator
from app.components.validators.pre_apply_readiness import PreApplyReadinessValidator
from app.components.validators.source_cell_verifier import SourceCellVerifier
from app.inferencing._base import Provider
from app.pipelines.tuning import PipelineTuning


def make_extract_pipeline(llm: Provider, tuning: PipelineTuning) -> Pipeline:
    """Build the per-sheet extraction Pipeline.

    Wires deterministic + LLM-backed Components via `pipeline.connect()` edges.
    Two-tier validation runs synchronously between LLM mutations: every agent
    that mutates plan or name_map is followed by a between-agents validator.
    """
    p = Pipeline()

    p.add_component("sheet_classifier", SheetClassifierAgent(llm=llm))
    p.add_component("planner", SheetRowPlanner())
    p.add_component("plan_invariants", PlanInvariantsValidator())
    p.add_component("plan_statistics", PlanStatisticsValidator())
    p.add_component("layout_hinter", LayoutHinterAgent(llm=llm))
    p.add_component("plan_reviewer", PlanReviewerAgent(llm=llm))
    p.add_component("post_review_plan", PostReviewPlanValidator())
    p.add_component("field_namer", FieldNamerAgent(llm=llm))
    p.add_component("post_namer_canonical", PostNamerCanonicalValidator())
    p.add_component("pre_apply_readiness", PreApplyReadinessValidator())
    p.add_component("applier", Applier())
    p.add_component("source_cell_verifier",
                     SourceCellVerifier(workbook_ctx=None))  # ctx supplied at run()
    p.add_component("header_match_verifier",
                     HeaderMatchVerifier(workbook_ctx=None))
    p.add_component("coverage_verifier", CoverageVerifier(boundaries=[]))
    p.add_component("field_dropout_verifier", FieldDropoutVerifier())
    p.add_component("reconciler", Reconciler())

    # planner → plan validators
    p.connect("planner.plan", "plan_invariants.plan")
    p.connect("planner.plan", "plan_statistics.plan")

    # plan → reviewer (always; the orchestrator passes findings through)
    p.connect("planner.plan", "plan_reviewer.plan")

    # reviewer corrections re-validate
    p.connect("plan_reviewer.plan", "post_review_plan.plan")

    # plan → namer (after review gate)
    p.connect("plan_reviewer.plan", "field_namer.plan")

    # namer output → canonical-coverage validator
    p.connect("planner.plan", "post_namer_canonical.plan")
    p.connect("field_namer.name_map", "post_namer_canonical.name_map")

    # ready-to-apply gate
    p.connect("plan_reviewer.plan", "pre_apply_readiness.plan")

    # applier
    p.connect("plan_reviewer.plan", "applier.plan")
    p.connect("field_namer.name_map", "applier.name_map")

    # extraction validators
    # (SourceCell / HeaderMatch / Coverage / FieldDropout are wired by the wrapping
    # extract() function once `extraction` is built from per-sheet `applier.plis`.)

    return p
```

- [ ] **F.3.2 Re-run pytest** — green (topology test).

- [ ] **F.3.3 Commit.**

```bash
git add app/pipelines/extract.py tests/integration/test_haystack_pipeline_wiring.py
git commit -m "feat(pipeline): add make_extract_pipeline factory with full topology"
```

---

## Task F.4 — Per-sheet driver `extract()` preserves root OTel span

**Files:**
- Modify: `app/pipelines/extract.py` — add `extract()` wrapper
- Test: `tests/integration/test_extract_pipeline_driver.py`

The Pipeline is per-sheet. The wrapping `extract()` function: registers workbook → calls `sheet_classifier` → iterates relevant sheets, calling the Pipeline once per sheet → aggregates PLIs → runs post-aggregation validators (Source/Header/Coverage/Dropout) → calls Reconciler. Root `extract` OTel span wraps everything (preserved for back-compat with existing trace queries).

- [ ] **F.4.1 Write failing test.**

```python
"""Integration test: extract() runs end-to-end with a FakeLLM."""
from __future__ import annotations
from pathlib import Path
from app.pipelines.extract import extract
from tests.fakes import FakeLLM


def test_extract_returns_result(sample_xlsx: Path) -> None:
    """extract() returns ExtractionResult and emits the root 'extract' span."""
    llm = FakeLLM()
    result = extract(sample_xlsx, llm=llm)
    assert result.source_file
```

- [ ] **F.4.2 Run pytest** — failure (`extract` not exposed yet).

- [ ] **F.4.3 Implement.**

Append to `app/pipelines/extract.py`:

```python
import time
from pathlib import Path
from typing import Any

import structlog.contextvars

from app.core.logs import get_logger
from app.core.telemetry import (
    extraction_duration_seconds, extraction_phase_duration_seconds,
    extraction_pli_count, extractions_total, plis_extracted_total,
)
from app.core.tracing import get_tracer
from app.inferencing.anthropic import AnthropicProvider
from app.models.artifacts import ValidationFindings
from app.models.extraction import ExtractionResult, PLI, Warning
from app.repositories.workbook_repo import register_workbook
from app.tools import get_tool

log = get_logger(__name__)


def extract(workbook_path: Path | str, *, llm: Provider | None = None,
            tuning: PipelineTuning | None = None) -> ExtractionResult:
    """Extract structured PLIs from a TNA workbook end-to-end via the Pipeline."""
    t0 = time.monotonic()
    ctx = register_workbook(workbook_path)
    llm = llm or AnthropicProvider.from_env()
    tuning = tuning or PipelineTuning()
    pipeline = make_extract_pipeline(llm=llm, tuning=tuning)

    with get_tracer(__name__).start_as_current_span("extract") as root_span:
        root_span.set_attribute("file", str(ctx.path))
        try:
            return _run_extract(ctx, pipeline, t0)
        except Exception:
            extractions_total.add(1, {"status": "failure"})
            raise


def _run_extract(ctx: Any, pipeline: Pipeline, t0: float) -> ExtractionResult:
    """Drive the per-sheet pipeline + post-aggregation validators."""
    summary = get_tool("workbook_summary")(ctx)
    sc_out = pipeline.run({"sheet_classifier": {"workbook_ctx": ctx,
                                                  "workbook_summary": summary}})
    relevant: list[str] = sc_out["sheet_classifier"]["relevant_sheets"]
    if not relevant:
        extractions_total.add(1, {"status": "empty"})
        return ExtractionResult(
            plis=[], source_file=str(ctx.path),
            warnings=[Warning(message="No relevant sheets identified",
                              severity="warning")],
        )

    all_plis, all_warnings, format_detected = _per_sheet_loop(ctx, pipeline, relevant)
    workflow = ExtractionResult(
        plis=all_plis, warnings=all_warnings,
        format_detected=format_detected, source_file=str(ctx.path),
    )
    findings = _run_extraction_validators(ctx, workflow)
    final = pipeline.get_component("reconciler").run(
        workflow=workflow, validation=findings,
    )["result"]
    _record_telemetry(ctx, final, t0)
    return final


def _per_sheet_loop(ctx: Any, pipeline: Pipeline,
                     relevant: list[str]) -> tuple[list[PLI], list[Warning], str | None]:
    """Run the per-sheet Pipeline once per relevant sheet, aggregating output."""
    all_plis: list[PLI] = []
    all_warnings: list[Warning] = []
    format_detected: str | None = None
    for sheet in relevant:
        sheet_out = pipeline.run({"planner": {"workbook_ctx": ctx, "sheet": sheet}})
        plis = sheet_out["applier"]["plis"]
        for pli in plis:
            if not pli.source.sheet:
                pli.source.sheet = sheet
        all_plis.extend(plis)
        # Findings from the between-agents + tier-1/2 validators attach as warnings
        for key in ("plan_invariants", "plan_statistics", "post_review_plan",
                    "post_namer_canonical", "pre_apply_readiness"):
            for f in sheet_out.get(key, {}).get("findings", []):
                all_warnings.append(Warning(message=f"{f.check}: {f.message}",
                                            severity="warning"))
        if format_detected is None:
            plan = sheet_out["planner"]["plan"]
            format_detected = plan.pli_mode.value
    return all_plis, all_warnings, format_detected


def _run_extraction_validators(ctx: Any, workflow: ExtractionResult) -> ValidationFindings:
    """Run the four post-aggregation extraction validators sequentially."""
    src = SourceCellVerifier(workbook_ctx=ctx).run(extraction=workflow)["findings"]
    hdr = HeaderMatchVerifier(workbook_ctx=ctx).run(extraction=workflow)["findings"]
    cov = CoverageVerifier(boundaries=[]).run(extraction=workflow)["findings"]
    drop = FieldDropoutVerifier().run(extraction=workflow)["findings"]
    return ValidationFindings(findings=(src.findings + hdr.findings
                                         + cov.findings + drop.findings))


def _record_telemetry(ctx: Any, final: ExtractionResult, t0: float) -> None:
    """Emit duration / count / status metrics for the completed extraction."""
    extraction_duration_seconds.record(
        time.monotonic() - t0,
        {"format_detected": final.format_detected or "unknown"},
    )
    extraction_pli_count.add(len(final.plis), {"source_file": ctx.path.name})
    status = "empty" if not final.plis else "success"
    extractions_total.add(1, {"status": status})
    plis_extracted_total.add(len(final.plis))
```

- [ ] **F.4.4 Re-run pytest** — green.

- [ ] **F.4.5 Commit.**

```bash
git add app/pipelines/extract.py \
        tests/integration/test_extract_pipeline_driver.py
git commit -m "feat(pipeline): add extract() driver that runs the Pipeline per sheet"
```

---

## Task F.5 — Haystack content-tracing per-component span test

**Files:**
- Test: `tests/integration/test_haystack_content_tracing.py`

- [ ] **F.5.1 Write failing test.**

```python
"""Asserts Haystack emits per-component spans with input/output attributes."""
from __future__ import annotations
import os
from pathlib import Path
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry import trace

from app.pipelines.extract import extract
from tests.fakes import FakeLLM


def test_per_component_spans_emitted(sample_xlsx: Path) -> None:
    """Each Component appears as a child span under the root 'extract' span."""
    os.environ["HAYSTACK_CONTENT_TRACING_ENABLED"] = "true"
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    extract(sample_xlsx, llm=FakeLLM())
    names = {span.name for span in exporter.get_finished_spans()}
    # 'extract' is the orchestrator-level span; Haystack emits one span per component
    assert "extract" in names
    assert any(n.startswith("haystack") or "planner" in n.lower() for n in names)
```

- [ ] **F.5.2 Run pytest** — should already pass if F.1 + F.4 are in place; otherwise iterate on env config.

- [ ] **F.5.3 Commit.**

```bash
git add tests/integration/test_haystack_content_tracing.py
git commit -m "test(observability): assert per-component spans emit with content tracing"
```

---

## Task F.6 — Checkpoint F (full eval baseline diff)

- [ ] **F.6.1 Verify.**

```bash
make test
make eval-smoke
make eval
```

Compare the latest `evals/runs/*.json` against `evals/runs/baseline-pre-pipeline-migration.json`:

```bash
python scripts/diff_eval_matrix.py \
  evals/runs/baseline-pre-pipeline-migration.json \
  evals/runs/$(ls -1t evals/runs/ | grep -v baseline | head -1)
```

Acceptance: every metric (pli_recall, field_precision_recall macro/micro, stage_recall, source_cell_match, header_match) is within ±1pp of baseline. If drift exceeds 1pp, debug before proceeding to Phase G.

- [ ] **F.6.2 Commit (matrix archive only).**

```bash
git add evals/runs/
git commit -m "chore(eval): archive post-pipeline-migration matrix vs baseline"
```

---

# Phase G — Router

## Task G.1 — Switch router to `app.pipelines.extract`

**Files:**
- Modify: `app/routers/extract.py`
- Test: `tests/integration/test_extract_router.py` — existing test should pass unchanged

- [ ] **G.1.1 Implement.**

```python
"""POST /extract — upload xlsx, run the Pipeline, return ExtractionResult."""
from __future__ import annotations
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.logs import get_logger
from app.pipelines.extract import extract
from app.schemas.extract import ExtractResponse

log = get_logger(__name__)
router = APIRouter()


@router.post("/extract", response_model=ExtractResponse, tags=["extract"])
async def extract_endpoint(file: UploadFile) -> ExtractResponse:
    """Extract structured PLI / Stage JSON from an uploaded TNA xlsx."""
    log.info("extract_request_received", filename=file.filename,
             content_type=file.content_type)
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="expected an .xlsx upload")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        body = await file.read()
        tmp.write(body)
        tmp_path = Path(tmp.name)
    try:
        result = extract(tmp_path)
    except Exception as e:
        log.exception("extract_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=f"extraction failed: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    log.info("extract_request_complete", filename=file.filename,
             pli_count=len(result.plis), warning_count=len(result.warnings))
    return ExtractResponse(**result.model_dump())
```

- [ ] **G.1.2 Run pytest** — green (router contract unchanged).

- [ ] **G.1.3 Commit.**

```bash
git add app/routers/extract.py
git commit -m "refactor(router): point /extract at app.pipelines.extract"
```

---

## Task G.2 — Checkpoint G

- [ ] **G.2.1 Verify.**

```bash
make test
```

Green.

---

# Phase H — Cleanup

## Task H.1 — Delete `app/services/`

Everything has moved. The orchestrator (`extraction.py`), planner, applier, reconciler, and validators are gone. Sub-plan 4 already removed `agents/` and sub-plan 2 already removed `llm_provider.py`.

- [ ] **H.1.1 Verify nothing imports `app.services.*`.**

```bash
grep -rn "from app.services" app tests docs && echo "STILL REFERENCED — FIX FIRST" || echo "OK"
```

- [ ] **H.1.2 Delete.**

```bash
git rm -r app/services/
```

- [ ] **H.1.3 Run pytest.**

```bash
make test
```

Green.

- [ ] **H.1.4 Commit.**

```bash
git commit -m "chore: retire app/services/ — pipeline + components are the new substrate"
```

---

## Task H.2 — Delete `app/repositories/workbook_tools/`

The legacy tools registry was replaced by `app/tools/` in Phase A.

- [ ] **H.2.1 Verify.**

```bash
grep -rn "workbook_tools" app tests && echo "STILL REFERENCED — FIX FIRST" || echo "OK"
```

- [ ] **H.2.2 Delete.**

```bash
git rm -r app/repositories/workbook_tools/
```

- [ ] **H.2.3 Run pytest, then commit.**

```bash
make test
git commit -m "chore: retire app/repositories/workbook_tools/ — replaced by app/tools/"
```

---

## Task H.3 — Delete `app/prompts/workflow/`

Sub-plan 4 moved each prompt to `app/prompts/<name>.py`. The legacy `.md` files in `workflow/` are no longer imported.

- [ ] **H.3.1 Verify.**

```bash
grep -rn "prompts/workflow\|prompts.workflow" app tests && echo "STILL REFERENCED — FIX FIRST" || echo "OK"
```

- [ ] **H.3.2 Delete.**

```bash
git rm -r app/prompts/workflow/
```

- [ ] **H.3.3 Run pytest, then commit.**

```bash
make test
git commit -m "chore: retire app/prompts/workflow/ — prompts are now Python modules"
```

---

# Phase I — Documentation + ADR

## Task I.1 — ADR-0007 — Pipeline architecture redesign

**Files:**
- Create: `docs/adrs/0007-pipeline-architecture-redesign.md`

- [ ] **I.1.1 Write the ADR.**

```markdown
# ADR-0007 — Pipeline architecture redesign

**Status:** Accepted
**Date:** 2026-05-21
**Supersedes:** none (extends ADR-0003 and ADR-0006)
**Spec:** `docs/superpowers/specs/2026-05-21-pipeline-architecture-redesign-design.md`

## Context

The codebase grew an ambiguous mix: `@component`-decorated agents and verifiers
co-located; tools lived in `repositories/workbook_tools/`; the orchestrator was
imperative Python that hand-wired phases; spans showed timing but no train of
thought. A reader could not answer "what kind of thing is this" from a file path.

## Decision

Adopt seven named primitives (pipeline / component / agent / tool / inferencing /
prompts / tuning_params), each with a single home in the file tree. Adopt
Haystack `Pipeline` + `@component` + `OpenTelemetryTracer` as the substrate;
build our own `Agent[Inputs, Output]` base with lifecycle hooks. Replace the
imperative orchestrator with a declarative `make_extract_pipeline()` factory.

## Consequences

**Positive**
- Per-component spans + I/O attributes flow automatically into SigNoz once
  `HAYSTACK_CONTENT_TRACING_ENABLED=true`.
- Train-of-thought capture (sub-plan 2) emits prompt + response per LLM call.
- Lifecycle hooks (sub-plan 3) replace single-point Pydantic validation with
  `validate_input` + `validate_output` per agent.
- New between-agents validators (`post_review_plan`, `post_namer_canonical`,
  `pre_apply_readiness`) close the multi-point-failure gap.
- `app/services/` no longer exists.

**Negative**
- Haystack Pipeline DSL is less linear than imperative Python; mitigated by
  keeping the factory function small and named.
- File count rose by ~20 (4 agents × 5 files each) — paid back by single-home-per-concept.

## Alternatives considered

- AgentScope / LangChain / Haystack `Agent` — wrong shape; see spec §3.
- Keeping imperative orchestrator with framework primitives "off to the side" —
  would have left two parallel substrates and split telemetry sources.

## Validation

Full `make eval` post-migration matches the pre-migration baseline within ±1pp on
every metric. See `evals/runs/baseline-pre-pipeline-migration.json` for the gate.
```

- [ ] **I.1.2 Commit.**

```bash
git add docs/adrs/0007-pipeline-architecture-redesign.md
git commit -m "docs(adr): add ADR-0007 pipeline architecture redesign"
```

---

## Task I.2 — Rewrite `ARCHITECTURE.md`

**Files:**
- Modify: `ARCHITECTURE.md`

- [ ] **I.2.1 Implement.**

Replace the "Layered structure" section with a seven-primitive view (pipeline / component / agent / tool / inferencing / prompts / tuning_params), each with its file-tree home and one-line role.

Replace the topology + phase diagrams with Haystack Pipeline wiring — show `make_extract_pipeline` connections (`pipeline.connect()` edges) instead of imperative phases.

Update the **Extension points** matrix:

| New thing arrives | Files you touch | Files you do **not** touch |
|---|---|---|
| New tool | 1× file under `app/tools/` (`@tool`-decorated) | components/agents that don't need it |
| New LLM agent | 1× `app/agents/<name>/` folder (5 files) + 1× edge in `make_extract_pipeline` | other agents |
| New deterministic component | 1× file under `app/components/` + 1× edge in pipeline | agents, validators |
| New between-agents validator | 1× file under `app/components/validators/` + 1× edge in pipeline | workflow side |
| New canonical PLI field | 1× field on `PLI` Pydantic + vocab in agent prompt module | apply_plan, eval |
| New layout family | rules inside `app/components/planner/<sub-component>.py` | agents, validators, pipeline factory |

Cross-link to ADR-0007 in the Locked design decisions table (add D11 row).

- [ ] **I.2.2 Commit.**

```bash
git add ARCHITECTURE.md
git commit -m "docs(architecture): rewrite for seven-primitive Pipeline shape"
```

---

## Task I.3 — `docs/CODING_STANDARD.md` §11 Framework primitives

**Files:**
- Modify: `docs/CODING_STANDARD.md`

- [ ] **I.3.1 Implement.**

Add §11 between today's §10 and the end of the document:

```markdown
## 11. Framework primitives

The seven primitives below have single homes. A reader must be able to answer
"what kind of thing is this" from the file path alone.

| Primitive | Home | One-line role |
|---|---|---|
| pipeline | `app/pipelines/<name>.py` | Top-level orchestration; Haystack `Pipeline` factory. No business logic. |
| component (det) | `app/components/<name>.py` | Deterministic unit; single `run()`; `@component`-decorated. |
| component (LLM) | `app/components/<name>.py` | Wraps an agent; same interface as det component. |
| agent | `app/agents/<name>/{agent,schema,tuning,validators}.py` | One narrow LLM mapping job. Folder layout fixed. |
| tool | `app/tools/<name>.py` | Side-effect-free helper; `@tool`-decorated; never called by an LLM. |
| inferencing | `app/inferencing/<provider>.py` | Single LLM call site; owns retry + train-of-thought capture. |
| prompts | `app/prompts/<name>.py` | One module-level string constant per prompt. |
| tuning_params | `app/agents/<name>/tuning.py` + `app/pipelines/tuning.py` | `pydantic-settings` blocks. |

**One folder per agent.** Every agent owns `agent.py`, `schema.py`, `tuning.py`,
`validators.py`. Tests live under `tests/unit/agents/<name>/`.

**Anti-patterns:**
- A `@component`-decorated class outside `app/components/` or `app/agents/<name>/`.
- A `@tool`-decorated function outside `app/tools/`.
- Direct provider calls outside `app/inferencing/`.
- A prompt as a `.md` file (use `app/prompts/<name>.py`).
```

Add to the §10 checklist a new sub-block:

```markdown
**Framework primitives (S11):**
- [ ] Every agent folder contains `agent.py`, `schema.py`, `tuning.py`, `validators.py`.
- [ ] `@tool`-decorated functions live only under `app/tools/`.
- [ ] `@component`-decorated classes live only under `app/components/` or `app/agents/`.
- [ ] No prompt is a `.md` file; every prompt is a `app/prompts/<name>.py` constant.
- [ ] No direct provider calls outside `app/inferencing/`.
```

- [ ] **I.3.2 Commit.**

```bash
git add docs/CODING_STANDARD.md
git commit -m "docs(standard): add §11 framework primitives + §10 checklist additions"
```

---

## Task I.4 — `docs/PRINCIPLES.md` cross-references

**Files:**
- Modify: `docs/PRINCIPLES.md`

- [ ] **I.4.1 Verify Principles 12 and 13 are present.** They were added in sub-plans 3 (lifecycle) and 2 (train-of-thought) respectively. If missing, add them per spec §9.

- [ ] **I.4.2 Implement cross-references.**

Append to Principle 4 (LLM as reviewer):

> See Principle 12 — Agent lifecycle base class is the enforcement mechanism;
> the convention is no longer just policy.

Append to Principle 11 (O(sheets) budget):

> The `decision_notes` extension (Principle 13) adds ~100–300 tokens per call
> but does not change call count — budget contract preserved.

- [ ] **I.4.3 Commit.**

```bash
git add docs/PRINCIPLES.md
git commit -m "docs(principles): cross-link principles 4/11 to 12/13"
```

---

## Self-review map (every spec requirement → task)

| Spec § | Requirement | Task(s) |
|---|---|---|
| §3 P1 pipeline | `make_extract_pipeline()` factory | F.3 |
| §3 P2 component | `@component` everywhere a unit runs | B.*, C.*, D.*, E.* |
| §3 P3 agent | folder layout per agent | (sub-plan 4; verified here in F.3 imports) |
| §3 P4 tool | move to `app/tools/`, `@tool` decorator | A.2–A.7 |
| §3 P5 inferencing | already in place | (sub-plan 2) |
| §3 P6 prompts | one module per prompt | (sub-plan 4; H.3 retires `prompts/workflow/`) |
| §3 P7 tuning_params | per-agent + pipeline | (sub-plan 1) |
| §5 between-agents validators | three new components | D.1–D.6 |
| §5 lifecycle two tiers | per-agent (sub-plan 3) + pipeline-level | D.* + C.1–C.6 |
| §6 file layout target | `app/services/` removed | H.1–H.3 |
| §10 sub-plan 5 tools migration | Phase A | A.* |
| §10 sub-plan 5 planner migration | Phase B | B.* |
| §10 sub-plan 5 validators migration | Phase C | C.* |
| §10 sub-plan 5 new validators | Phase D | D.* |
| §10 sub-plan 5 applier + reconciler | Phase E | E.1–E.3 |
| §10 sub-plan 5 Haystack Pipeline factory | Phase F | F.2–F.4 |
| §10 sub-plan 5 router | Phase G | G.1 |
| §10 sub-plan 5 retire `app/services/` | Phase H | H.1–H.3 |
| §10 sub-plan 5 `HAYSTACK_CONTENT_TRACING_ENABLED` | F.1 | F.1 |
| §10 sub-plan 5 ADR-0007 | I.1 | I.1 |
| §10 sub-plan 5 ARCHITECTURE rewrite | I.2 | I.2 |
| §10 sub-plan 5 CODING_STANDARD §11 | I.3 | I.3 |
| §10 sub-plan 5 PRINCIPLES cross-refs | I.4 | I.4 |
| Exit criterion: full `make eval` green vs baseline | F.6 | F.6 |
| Exit criterion: per-component spans visible | F.5 | F.5 |

**Final invariant after Phase I:** `find app/services -type f` returns nothing; `find app/repositories/workbook_tools -type f` returns nothing; `find app/prompts/workflow -type f` returns nothing; `docs/adrs/0007-pipeline-architecture-redesign.md` exists; `ARCHITECTURE.md` shows the seven-primitive view; `make test` and `make eval` are green; `make eval` matrix is within ±1pp of `evals/runs/baseline-pre-pipeline-migration.json`.
