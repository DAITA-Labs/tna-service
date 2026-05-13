# Test Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the existing 154-test corpus onto the unified 5-tier strategy described in `docs/superpowers/specs/2026-05-13-test-strategy-design.md`. New layout: `tests/{unit,flow,agent,e2e,live}/`. Fixture-driven (Python builders + tier-keyed expected.json) with first-class failure-case coverage and written conventions.

**Architecture:** Each test scenario lives in `tests/fixtures/builders/<name>.py` (Python `build(wb)` function) plus `tests/fixtures/expected/<name>.json` (tier-keyed assertions). Tests use `@fixture_case("<name>")` decorator to opt in. `FakeLLM` stub handles agent/e2e tiers; real Anthropic API only in live tier. Function-scoped pytest fixtures guarantee isolation per test.

**Tech Stack:** Python 3.11+, pytest, openpyxl, Pydantic v2, existing `app/repositories/workbook_repo.register_workbook` cache.

**Conventions:**
- Tests use `.venv/Scripts/python.exe -m pytest tests -q` (Windows project venv).
- No task/plan refs in code comments.
- Commits at the end of every task.
- No xlsx binary files under `tests/fixtures/` — only Python builders.

---

## File structure

**New scaffolding (Phase A):**
- `tests/fixtures/__init__.py` (empty)
- `tests/fixtures/builders/__init__.py` (empty)
- `tests/fixtures/expected/` (directory, no `__init__.py` since it's JSON only)
- `tests/fixtures/case.py` — `FixtureCase` dataclass + `fixture_case` decorator
- `tests/fixtures/fake_llm.py` — `FakeLLM` stub
- `tests/fixtures/conftest.py` — `fixture` pytest fixture
- `tests/flow/__init__.py`, `tests/agent/__init__.py`, `tests/e2e/__init__.py`, `tests/live/__init__.py` (all empty)
- `tests/unit/structure/__init__.py`, `tests/unit/repositories/__init__.py`

**Fixture pool (Phase B):**
- 6 positive anchors: `sheet_per_pli_clean`, `row_per_pli_with_merges`, `section_per_pli_two_blocks`, `tabular_simple`, `tabular_with_totals`, `tabular_repeat_header`
- 6 failure anchors: `tabular_corrupt_no_identity_col`, `workbook_only_title_row`, `plan_invariant_dangling_anchor`, `apply_name_map_missing_required`, `agent_returns_invalid_json`, `stage_band_low_date_density`
- Each = `builders/<name>.py` + `expected/<name>.json`

**Test moves (Phase C):**
- `tests/regression/test_christian_berg.py` → `tests/live/test_christian_berg.py`
- `tests/regression/test_new_job_tna.py` → `tests/live/test_new_job_tna.py`
- `tests/integration/test_e2e_live.py` → `tests/live/test_dataset_acceptance.py`
- `tests/integration/test_acceptance_extensibility.py` → `tests/unit/structure/test_layout.py`
- `tests/repositories/` → `tests/unit/repositories/`
- Delete empty `tests/regression/` and `tests/integration/`

**Test rewrites (Phase D, E):**
- `tests/unit/applier/test_apply_plan_{row,sheet_is,section}_per_pli.py` → `tests/flow/`
- `tests/unit/planner/test_plan.py` → `tests/flow/test_planner_pipeline.py`
- `tests/unit/agents/test_*.py` → `tests/agent/`

**New failure-case tests (Phase F):**
- `tests/flow/test_failure_planner_ambiguity.py`
- `tests/flow/test_failure_plan_invariants.py`
- `tests/flow/test_failure_data_anomalies.py`
- `tests/e2e/test_failure_input_validation.py`
- `tests/e2e/test_failure_apply_mismatches.py`
- `tests/agent/test_failure_agent_degradation.py`

**Rules doc (Phase G):**
- `docs/TESTING.md` (new)
- `docs/SPEC.md` § Testing strategy (update to link)

---

## Phase A — Scaffolding

### Task 1: Create directory skeleton and empty `__init__.py` markers

**Files:**
- Create: `tests/fixtures/__init__.py`, `tests/fixtures/builders/__init__.py`
- Create: `tests/fixtures/expected/.gitkeep` (since directory has no Python module)
- Create: `tests/flow/__init__.py`, `tests/agent/__init__.py`, `tests/e2e/__init__.py`, `tests/live/__init__.py`
- Create: `tests/unit/structure/__init__.py`

- [ ] **Step 1: Create the directories with empty markers**

```bash
mkdir -p tests/fixtures/builders tests/fixtures/expected tests/flow tests/agent tests/e2e tests/live tests/unit/structure
touch tests/fixtures/__init__.py tests/fixtures/builders/__init__.py
touch tests/fixtures/expected/.gitkeep
touch tests/flow/__init__.py tests/agent/__init__.py tests/e2e/__init__.py tests/live/__init__.py
touch tests/unit/structure/__init__.py
```

(On Windows PowerShell, equivalent: `New-Item -ItemType File -Path tests/fixtures/__init__.py -Force` per file. Bash via the project's Bash tool works too.)

- [ ] **Step 2: Verify the existing test suite still passes**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```
Expected: 154 passed (or current baseline).

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures tests/flow tests/agent tests/e2e tests/live tests/unit/structure
git commit -m "test(scaffold): directory skeleton for 5-tier strategy"
```

---

### Task 2: `FakeLLM` stub helper

**Files:**
- Create: `tests/fixtures/fake_llm.py`
- Create: `tests/fixtures/test_fake_llm.py` (the helper itself gets tested)

- [ ] **Step 1: Write the failing test**

```python
# tests/fixtures/test_fake_llm.py
"""Tests for the FakeLLM helper itself."""
import pytest
from pydantic import BaseModel
from tests.fixtures.fake_llm import FakeLLM


class _SchemaA(BaseModel):
    name: str


def test_fake_llm_returns_canned_response():
    llm = FakeLLM(canned={"_SchemaA": {"name": "hello"}})
    out = llm.complete_with_schema(system="s", user="u",
                                  output_schema=_SchemaA)
    assert isinstance(out, _SchemaA)
    assert out.name == "hello"


def test_fake_llm_raises_when_schema_not_canned():
    llm = FakeLLM(canned={})
    with pytest.raises(AssertionError, match="no canned response for schema"):
        llm.complete_with_schema(system="s", user="u",
                                output_schema=_SchemaA)
```

- [ ] **Step 2: Run, expect FAIL**

```
.venv/Scripts/python.exe -m pytest tests/fixtures/test_fake_llm.py -q
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# tests/fixtures/fake_llm.py
"""LLMProvider stub for tests — returns canned values keyed by output schema name.

Mirrors the LLMProvider Protocol's complete_with_schema signature so the
production AgentRunner can use it without modification.
"""
from __future__ import annotations
from typing import Any


class FakeLLM:
    def __init__(self, canned: dict[str, dict]):
        self._canned = canned

    def complete_with_schema(self, system: str, user: str,
                            output_schema: type, tool_name: str | None = None) -> Any:
        name = output_schema.__name__
        if name not in self._canned:
            raise AssertionError(
                f"FakeLLM has no canned response for schema {name!r}. "
                f"Available: {sorted(self._canned)}"
            )
        return output_schema(**self._canned[name])
```

- [ ] **Step 4: Run, expect PASS**

```
.venv/Scripts/python.exe -m pytest tests/fixtures/test_fake_llm.py -q
```
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/fake_llm.py tests/fixtures/test_fake_llm.py
git commit -m "test(fixtures): FakeLLM stub with canned-response lookup"
```

---

### Task 3: `FixtureCase` dataclass + `fixture_case` decorator

**Files:**
- Create: `tests/fixtures/case.py`
- Create: `tests/fixtures/test_case.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/fixtures/test_case.py
"""Tests for the FixtureCase helper itself."""
import pytest
from tests.fixtures.case import FixtureCase


def _make_case(expected: dict) -> FixtureCase:
    return FixtureCase(name="dummy", ctx=None, xlsx_path=None, _expected=expected)


def test_fixture_case_expectations_returns_tier_section():
    c = _make_case({"layer_expectations": {"flow": {"pli_mode": "row_per_pli"}}})
    assert c.expectations("flow") == {"pli_mode": "row_per_pli"}


def test_fixture_case_expectations_raises_when_tier_missing():
    c = _make_case({"layer_expectations": {"flow": {}}})
    with pytest.raises(AssertionError, match="no `layer_expectations.agent`"):
        c.expectations("agent")


def test_fixture_case_is_failure_case_detects_block():
    c1 = _make_case({"layer_expectations": {}})
    c2 = _make_case({"layer_expectations": {}, "failure_expectations": {"category": "x"}})
    assert c1.is_failure_case() is False
    assert c2.is_failure_case() is True


def test_fixture_case_description_default():
    c = _make_case({"layer_expectations": {}})
    assert c.description == ""
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement**

```python
# tests/fixtures/case.py
"""FixtureCase: a single test scenario, materialized.

The `fixture` pytest fixture (in conftest.py) builds FixtureCase instances
from a fixture name. Tests consume FixtureCase to read ctx / sheets / 
expected assertions.

`fixture_case(*names)` is sugar over @pytest.mark.parametrize so tests can
declare which scenarios they run against without re-typing the parametrize
incantation.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import pytest


@dataclass(frozen=True)
class FixtureCase:
    name: str
    ctx: Any
    xlsx_path: Path | None
    _expected: dict

    @property
    def sheets(self) -> list[str]:
        return list(self.ctx.wb.sheetnames) if self.ctx is not None else []

    @property
    def sheet(self) -> str:
        if not self.sheets:
            raise AssertionError(f"Fixture {self.name!r} has no sheets")
        return self.sheets[0]

    @property
    def description(self) -> str:
        return self._expected.get("description", "")

    def expectations(self, tier: str) -> dict:
        per_tier = (self._expected.get("layer_expectations") or {}).get(tier)
        if per_tier is None:
            raise AssertionError(
                f"Fixture {self.name!r} has no `layer_expectations.{tier}` "
                f"declared in expected.json"
            )
        return per_tier

    def failure_expectations(self) -> dict | None:
        return self._expected.get("failure_expectations")

    def is_failure_case(self) -> bool:
        return self.failure_expectations() is not None

    def fake_llm_responses(self) -> dict:
        return self.expectations("e2e").get("fake_llm_responses", {})


def fixture_case(*names: str):
    """Parametrize the test over named fixtures.

    Usage:
        @fixture_case("tabular_simple")
        def test_one(fixture):
            ...

        @fixture_case("tabular_simple", "tabular_with_totals")
        def test_many(fixture):
            ...
    """
    if not names:
        raise ValueError("@fixture_case requires at least one fixture name")
    return pytest.mark.parametrize("fixture", names, indirect=True, ids=list(names))
```

- [ ] **Step 4: Run, expect PASS**

```
.venv/Scripts/python.exe -m pytest tests/fixtures/test_case.py -q
```
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/case.py tests/fixtures/test_case.py
git commit -m "test(fixtures): FixtureCase dataclass + fixture_case decorator"
```

---

### Task 4: `tests/fixtures/conftest.py` — the `fixture` pytest fixture

**Files:**
- Create: `tests/fixtures/conftest.py`
- Create: `tests/fixtures/builders/_smoke.py` (minimal builder, only used to test the loader)
- Create: `tests/fixtures/expected/_smoke.json`
- Create: `tests/fixtures/test_conftest_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/fixtures/test_conftest_loader.py
"""Tests for the conftest-defined `fixture` pytest fixture."""
import pytest
from tests.fixtures.case import fixture_case


@fixture_case("_smoke")
def test_loader_materializes_xlsx_and_parses_expected(fixture):
    assert fixture.name == "_smoke"
    assert fixture.xlsx_path is not None
    assert fixture.xlsx_path.exists()
    assert fixture.expectations("flow") == {"pli_mode": "row_per_pli"}
```

- [ ] **Step 2: Add the smoke builder + expected.json**

```python
# tests/fixtures/builders/_smoke.py
"""Minimal builder used to verify the conftest loader."""
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "IO NO"
    ws["A2"] = 1
```

```json
{
  "fixture": "_smoke",
  "description": "Minimal smoke fixture used by conftest loader tests.",
  "layer_expectations": {
    "flow": {
      "pli_mode": "row_per_pli"
    }
  },
  "failure_expectations": null
}
```

Save the JSON to `tests/fixtures/expected/_smoke.json`.

- [ ] **Step 3: Implement the conftest loader**

```python
# tests/fixtures/conftest.py
"""Pytest fixture loader for the FixtureCase system.

`fixture(request, tmp_path)` is indirectly parametrized via @fixture_case.
The parameter is a builder name. The loader:
  1. Imports tests.fixtures.builders.<name>.
  2. Builds a fresh Workbook in tmp_path.
  3. Loads tests/fixtures/expected/<name>.json.
  4. Registers via register_workbook for a fresh ctx.
  5. clear_cache() at setup AND teardown for isolation.

Builders may export `build(wb)` (xlsx workbook) OR `build_plan() -> SheetPlan`
(synthetic plan, used for plan-invariant failure cases). The loader detects
which is present.
"""
from __future__ import annotations
import importlib
import json
from pathlib import Path
import pytest
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from tests.fixtures.case import FixtureCase

FIXTURES_ROOT = Path(__file__).resolve().parent
BUILDERS_DIR = FIXTURES_ROOT / "builders"
EXPECTED_DIR = FIXTURES_ROOT / "expected"


@pytest.fixture
def fixture(request, tmp_path) -> FixtureCase:
    name = request.param
    builder_path = BUILDERS_DIR / f"{name}.py"
    expected_path = EXPECTED_DIR / f"{name}.json"
    if not builder_path.exists():
        raise AssertionError(f"Fixture builder not found: {builder_path}")
    if not expected_path.exists():
        raise AssertionError(f"Fixture expected.json not found: {expected_path}")

    clear_cache()
    builder_mod = importlib.import_module(f"tests.fixtures.builders.{name}")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    if expected.get("fixture", name) != name:
        raise AssertionError(
            f"expected.json `fixture` field mismatch: {expected.get('fixture')} != {name}"
        )

    if hasattr(builder_mod, "build_plan"):
        ctx = None
        xlsx_path = None
    else:
        wb = Workbook()
        builder_mod.build(wb)
        xlsx_path = tmp_path / f"{name}.xlsx"
        wb.save(xlsx_path)
        ctx = register_workbook(xlsx_path)

    yield FixtureCase(name=name, ctx=ctx, xlsx_path=xlsx_path, _expected=expected)
    clear_cache()
```

- [ ] **Step 4: Run the loader test**

```
.venv/Scripts/python.exe -m pytest tests/fixtures/test_conftest_loader.py -q
```
Expected: `1 passed`.

- [ ] **Step 5: Verify nothing else broke**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```
Expected: 154+ passed.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/conftest.py tests/fixtures/builders/_smoke.py tests/fixtures/expected/_smoke.json tests/fixtures/test_conftest_loader.py
git commit -m "test(fixtures): conftest loader + smoke builder for verification"
```

---

### Task 5: Verify scaffolding is complete (regression check)

- [ ] **Step 1: Run full suite**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```
Expected: ≥155 passed (154 baseline + the new helper tests).

- [ ] **Step 2: Verify directories**

```bash
ls tests/fixtures
ls tests/fixtures/builders
ls tests/fixtures/expected
ls tests/flow tests/agent tests/e2e tests/live
ls tests/unit/structure
```

All directories should exist with `__init__.py` (and `_smoke.py` / `_smoke.json` in the fixture pool).

- [ ] **Step 3: No commit (verification only)**

---

## Phase B — Build the fixture pool

For Phase B, each task adds 3 fixtures (builder + expected.json). After each task, the suite runs to confirm no regressions.

### Task 6: Positive anchors — simple tabular family

Three fixtures: `tabular_simple`, `tabular_with_totals`, `tabular_repeat_header`.

**Files:**
- Create: `tests/fixtures/builders/tabular_simple.py`
- Create: `tests/fixtures/builders/tabular_with_totals.py`
- Create: `tests/fixtures/builders/tabular_repeat_header.py`
- Create: `tests/fixtures/expected/tabular_simple.json`
- Create: `tests/fixtures/expected/tabular_with_totals.json`
- Create: `tests/fixtures/expected/tabular_repeat_header.json`

- [ ] **Step 1: Author `tabular_simple` (builder + expected.json)**

```python
# tests/fixtures/builders/tabular_simple.py
"""Flat tabular layout: header row + 3 data rows, no merges, no totals.

Family 1 anchor — GUESS ATHLEISURE-style.
"""
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "IO NO"
    ws["B1"] = "STYLE"
    ws["C1"] = "ORDER QTY"
    ws["A2"] = "1063"; ws["B2"] = "DWJE"; ws["C2"] = 2000
    ws["A3"] = "1064"; ws["B3"] = "DWJF"; ws["C3"] = 1500
    ws["A4"] = "1065"; ws["B4"] = "DWJG"; ws["C4"] = 3000
```

```json
{
  "fixture": "tabular_simple",
  "description": "Flat tabular layout — 3 PLIs, no merges, no totals.",
  "layer_expectations": {
    "flow": {
      "pli_mode": "row_per_pli",
      "identity_column": "A",
      "anchor_count": 3,
      "child_count": 0,
      "total_count": 0,
      "kv_anchor_count": 0,
      "header_rows": [1]
    },
    "e2e": {
      "fake_llm_responses": {
        "SheetClassifierOutput": {"relevant_sheets": ["S"]},
        "CanonicalNameMap": {
          "field_labels": {"IO NO": "io_number", "STYLE": "style_code", "ORDER QTY": "quantity"},
          "stage_names": {}
        },
        "LayoutHints": {},
        "PlanVerdict": {"verdict": "looks_correct"}
      },
      "pli_count": 3,
      "io_numbers": ["1063", "1064", "1065"]
    }
  },
  "failure_expectations": null
}
```

- [ ] **Step 2: Author `tabular_with_totals`**

```python
# tests/fixtures/builders/tabular_with_totals.py
"""Tabular layout with merged identity per IO and an interleaved total row.

Family 2 anchor — CHRISTIAN BERG-style at a minimal scale.
2 IO groups: IO 1063 has 2 colors, IO 1064 has 1 color, plus 2 total rows.
"""
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "S NO"; ws["B1"] = "IO NO"; ws["K1"] = "COLOR"; ws["L1"] = "ORDER QTY"
    ws["A2"] = 1; ws["B2"] = "1063"; ws["K2"] = "MAGENTA"; ws["L2"] = 1000
    ws["K3"] = "NAVY"; ws["L3"] = 1000
    ws["L4"] = 2000              # total for group 0
    ws["A5"] = 2; ws["B5"] = "1064"; ws["K5"] = "PINE"; ws["L5"] = 1500
    ws["L6"] = 1500              # total for group 1
    ws.merge_cells("A2:A3"); ws.merge_cells("B2:B3")
```

```json
{
  "fixture": "tabular_with_totals",
  "description": "Vertical merge + interleaved totals, 2 IOs.",
  "layer_expectations": {
    "flow": {
      "pli_mode": "row_per_pli",
      "identity_column": "B",
      "anchor_count": 2,
      "child_count": 1,
      "total_count": 2,
      "kv_anchor_count": 0,
      "header_rows": [1]
    },
    "e2e": {
      "fake_llm_responses": {
        "SheetClassifierOutput": {"relevant_sheets": ["S"]},
        "CanonicalNameMap": {
          "field_labels": {"IO NO": "io_number", "COLOR": "color_code", "ORDER QTY": "quantity"},
          "stage_names": {}
        },
        "LayoutHints": {},
        "PlanVerdict": {"verdict": "looks_correct"}
      },
      "pli_count": 3,
      "io_numbers": ["1063", "1063", "1064"]
    }
  },
  "failure_expectations": null
}
```

- [ ] **Step 3: Author `tabular_repeat_header`**

```python
# tests/fixtures/builders/tabular_repeat_header.py
"""Tabular layout with a repeated header row mid-data.

Family 4 anchor — NORTHERN REFLECTIONS-style.
"""
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "IO NO"; ws["B1"] = "COLOR"
    ws["A2"] = "1063"; ws["B2"] = "MAGENTA"
    ws["A3"] = "1064"; ws["B3"] = "NAVY"
    ws["A4"] = "IO NO"; ws["B4"] = "COLOR"     # repeat header
    ws["A5"] = "1065"; ws["B5"] = "PINE"
```

```json
{
  "fixture": "tabular_repeat_header",
  "description": "Repeat header row at idx 4 between data rows.",
  "layer_expectations": {
    "flow": {
      "pli_mode": "row_per_pli",
      "identity_column": "A",
      "anchor_count": 3,
      "child_count": 0,
      "repeat_header_count": 1,
      "header_rows": [1]
    },
    "e2e": {
      "fake_llm_responses": {
        "SheetClassifierOutput": {"relevant_sheets": ["S"]},
        "CanonicalNameMap": {
          "field_labels": {"IO NO": "io_number", "COLOR": "color_code"},
          "stage_names": {}
        },
        "LayoutHints": {},
        "PlanVerdict": {"verdict": "looks_correct"}
      },
      "pli_count": 3,
      "io_numbers": ["1063", "1064", "1065"]
    }
  },
  "failure_expectations": null
}
```

- [ ] **Step 4: Verify each loads cleanly**

Write a temporary loader smoke test (will be replaced by real flow tests later):

```python
# tests/fixtures/test_fixture_pool_phase_b1.py
"""Smoke-test that the Phase B1 fixtures load via the conftest loader."""
from tests.fixtures.case import fixture_case


@fixture_case("tabular_simple", "tabular_with_totals", "tabular_repeat_header")
def test_phase_b1_fixtures_load(fixture):
    assert fixture.xlsx_path is not None
    assert fixture.xlsx_path.exists()
    assert "flow" in fixture._expected["layer_expectations"]
    assert "e2e" in fixture._expected["layer_expectations"]
```

Run:
```
.venv/Scripts/python.exe -m pytest tests/fixtures/test_fixture_pool_phase_b1.py -q
```
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/builders/tabular_simple.py tests/fixtures/builders/tabular_with_totals.py tests/fixtures/builders/tabular_repeat_header.py tests/fixtures/expected/tabular_simple.json tests/fixtures/expected/tabular_with_totals.json tests/fixtures/expected/tabular_repeat_header.json tests/fixtures/test_fixture_pool_phase_b1.py
git commit -m "test(fixtures): tabular_simple, tabular_with_totals, tabular_repeat_header anchors"
```

---

### Task 7: Positive anchors — complex layout families

Three fixtures: `sheet_per_pli_clean`, `row_per_pli_with_merges`, `section_per_pli_two_blocks`.

**Files:**
- Create: `tests/fixtures/builders/sheet_per_pli_clean.py`
- Create: `tests/fixtures/builders/row_per_pli_with_merges.py`
- Create: `tests/fixtures/builders/section_per_pli_two_blocks.py`
- Create: matching `expected/*.json` files

- [ ] **Step 1: Author `sheet_per_pli_clean`**

```python
# tests/fixtures/builders/sheet_per_pli_clean.py
"""3-sheet workbook where each sheet is a single PLI with KV identity.

Family 5 anchor — new job-TNA.xlsx style.
"""
from datetime import datetime
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    for job in ["63315", "63306", "63305"]:
        ws = wb.create_sheet(job)
        ws["A4"] = "Job No"; ws["B4"] = int(job)
        ws["A5"] = "Quantity"; ws["B5"] = 100000
        ws["A8"] = "Pre-Prod TNA"
        ws["C8"] = "L/D send"; ws["D8"] = "Fit send"
        ws["C9"] = datetime(2026, 3, 1)
        ws["D9"] = datetime(2026, 3, 5)
```

```json
{
  "fixture": "sheet_per_pli_clean",
  "description": "3 sheets, each a single PLI with scattered KV identity and one stage band.",
  "layer_expectations": {
    "flow": {
      "pli_mode": "sheet_is_pli",
      "kv_anchor_count_per_sheet": [2, 2, 2],
      "stage_band_count_per_sheet": [1, 1, 1]
    },
    "e2e": {
      "fake_llm_responses": {
        "SheetClassifierOutput": {"relevant_sheets": ["63315", "63306", "63305"]},
        "CanonicalNameMap": {
          "field_labels": {"Job No": "io_number", "Quantity": "quantity"},
          "stage_names": {"L/D send": "lab_dip_send", "Fit send": "fit_send"}
        },
        "LayoutHints": {},
        "PlanVerdict": {"verdict": "looks_correct"}
      },
      "pli_count": 3,
      "io_numbers": ["63315", "63306", "63305"],
      "stage_count_per_pli": [2, 2, 2]
    }
  },
  "failure_expectations": null
}
```

- [ ] **Step 2: Author `row_per_pli_with_merges`**

```python
# tests/fixtures/builders/row_per_pli_with_merges.py
"""Vertical-merge layout: 2 IOs, each with 2-3 color child rows.

Family 2 anchor — Compass Pro / MAIN FALL KIDS style.
"""
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "S NO"; ws["B1"] = "IO NO"; ws["K1"] = "COLOR"; ws["L1"] = "ORDER QTY"
    ws["A2"] = 1; ws["B2"] = "1063"; ws["K2"] = "MAGENTA"; ws["L2"] = 1000
    ws["K3"] = "NAVY"; ws["L3"] = 1000
    ws["K4"] = "WHITE"; ws["L4"] = 1000
    ws["A5"] = 2; ws["B5"] = "1064"; ws["K5"] = "PINE"; ws["L5"] = 1500
    ws["K6"] = "GRAY"; ws["L6"] = 1500
    ws.merge_cells("A2:A4"); ws.merge_cells("B2:B4")
    ws.merge_cells("A5:A6"); ws.merge_cells("B5:B6")
```

```json
{
  "fixture": "row_per_pli_with_merges",
  "description": "2 IOs with vertical-merge identity, 5 color rows total.",
  "layer_expectations": {
    "flow": {
      "pli_mode": "row_per_pli",
      "identity_column": "B",
      "anchor_count": 2,
      "child_count": 3,
      "total_count": 0,
      "header_rows": [1]
    },
    "e2e": {
      "fake_llm_responses": {
        "SheetClassifierOutput": {"relevant_sheets": ["S"]},
        "CanonicalNameMap": {
          "field_labels": {"IO NO": "io_number", "COLOR": "color_code", "ORDER QTY": "quantity"},
          "stage_names": {}
        },
        "LayoutHints": {},
        "PlanVerdict": {"verdict": "looks_correct"}
      },
      "pli_count": 5,
      "io_numbers": ["1063", "1063", "1063", "1064", "1064"]
    }
  },
  "failure_expectations": null
}
```

- [ ] **Step 3: Author `section_per_pli_two_blocks`**

```python
# tests/fixtures/builders/section_per_pli_two_blocks.py
"""Two PLI blocks separated by a blank-row gap. Each block has its own
KV identity + a local stage band."""
from datetime import datetime
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A4"] = "IO"; ws["B4"] = "1063"
    ws["C8"] = "Cut"; ws["D8"] = "Sew"
    ws["C9"] = datetime(2026, 3, 12); ws["D9"] = datetime(2026, 4, 3)
    ws["A14"] = "IO"; ws["B14"] = "1064"
    ws["C18"] = "Cut"; ws["D18"] = "Sew"
    ws["C19"] = datetime(2026, 4, 16); ws["D19"] = datetime(2026, 4, 25)
```

```json
{
  "fixture": "section_per_pli_two_blocks",
  "description": "Two PLI blocks separated by a blank-row gap.",
  "layer_expectations": {
    "flow": {
      "pli_mode_acceptable": ["section_per_pli", "row_per_pli"],
      "pli_count_min": 2,
      "pli_count_max": 2
    },
    "e2e": {
      "fake_llm_responses": {
        "SheetClassifierOutput": {"relevant_sheets": ["S"]},
        "CanonicalNameMap": {
          "field_labels": {"IO": "io_number"},
          "stage_names": {"Cut": "cutting", "Sew": "sewing"}
        },
        "LayoutHints": {},
        "PlanVerdict": {"verdict": "looks_correct"}
      },
      "pli_count": 2,
      "io_numbers": ["1063", "1064"]
    }
  },
  "failure_expectations": null
}
```

Note: `pli_mode_acceptable` is a list because the planner's mode-decision heuristic may not always pick SECTION_PER_PLI for sparse blocks; the test accepts either as long as the PLI count is right.

- [ ] **Step 4: Smoke-test the new fixtures load**

```python
# tests/fixtures/test_fixture_pool_phase_b2.py
from tests.fixtures.case import fixture_case


@fixture_case("sheet_per_pli_clean", "row_per_pli_with_merges", "section_per_pli_two_blocks")
def test_phase_b2_fixtures_load(fixture):
    assert fixture.xlsx_path.exists()
    assert "flow" in fixture._expected["layer_expectations"]
    assert "e2e" in fixture._expected["layer_expectations"]
```

Run:
```
.venv/Scripts/python.exe -m pytest tests/fixtures/test_fixture_pool_phase_b2.py -q
```
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/builders/sheet_per_pli_clean.py tests/fixtures/builders/row_per_pli_with_merges.py tests/fixtures/builders/section_per_pli_two_blocks.py tests/fixtures/expected/sheet_per_pli_clean.json tests/fixtures/expected/row_per_pli_with_merges.json tests/fixtures/expected/section_per_pli_two_blocks.json tests/fixtures/test_fixture_pool_phase_b2.py
git commit -m "test(fixtures): sheet_per_pli_clean, row_per_pli_with_merges, section_per_pli_two_blocks anchors"
```

---

### Task 8: Failure anchors — input validation + planner ambiguity + data anomaly

Three fixtures:
- `workbook_only_title_row` (input validation)
- `tabular_corrupt_no_identity_col` (planner ambiguity)
- `stage_band_low_date_density` (data anomaly)

- [ ] **Step 1: Author `workbook_only_title_row`**

```python
# tests/fixtures/builders/workbook_only_title_row.py
"""Sheet that's just a title row — no data, no headers."""
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "JUST A TITLE, NO DATA"
```

```json
{
  "fixture": "workbook_only_title_row",
  "description": "Sheet contains only a title row; no extractable PLIs.",
  "layer_expectations": {
    "flow": {
      "anchor_count": 0,
      "child_count": 0
    },
    "e2e": {
      "fake_llm_responses": {
        "SheetClassifierOutput": {"relevant_sheets": ["S"]},
        "CanonicalNameMap": {"field_labels": {}, "stage_names": {}},
        "LayoutHints": {},
        "PlanVerdict": {"verdict": "looks_correct"}
      },
      "pli_count": 0,
      "warning_count_min": 0
    }
  },
  "failure_expectations": {
    "category": "input_validation",
    "graceful_degradation": true,
    "must_not_raise": true
  }
}
```

- [ ] **Step 2: Author `tabular_corrupt_no_identity_col`**

```python
# tests/fixtures/builders/tabular_corrupt_no_identity_col.py
"""Tabular sheet whose header row has no IO/JOB/PO column.

Triggers planner ambiguity: no identity_col_candidates.
"""
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "NAME"; ws["B1"] = "DESCRIPTION"; ws["C1"] = "NOTES"
    ws["A2"] = "thing1"; ws["B2"] = "first thing"; ws["C2"] = "no notes"
    ws["A3"] = "thing2"; ws["B3"] = "second thing"; ws["C3"] = "more notes"
```

```json
{
  "fixture": "tabular_corrupt_no_identity_col",
  "description": "Header row has no canonical identity column (no IO/JOB/PO).",
  "layer_expectations": {
    "flow": {
      "anchor_count": 0,
      "plan_statistics_warnings_must_contain": ["pli_count_sanity"]
    },
    "e2e": {
      "fake_llm_responses": {
        "SheetClassifierOutput": {"relevant_sheets": ["S"]},
        "LayoutHints": {"identity_column_suggestion": null},
        "PlanVerdict": {"verdict": "looks_correct"},
        "CanonicalNameMap": {"field_labels": {}, "stage_names": {}}
      },
      "pli_count": 0,
      "warning_count_min": 1
    }
  },
  "failure_expectations": {
    "category": "planner_ambiguity",
    "expected_warning_check": "pli_count_sanity",
    "fires_layout_hinter": true,
    "graceful_degradation": true
  }
}
```

- [ ] **Step 3: Author `stage_band_low_date_density`**

```python
# tests/fixtures/builders/stage_band_low_date_density.py
"""Sheet with a stage band whose columns hold mostly strings, not dates.

Triggers Tier 2 date_band_density warning.
"""
from datetime import datetime
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "IO NO"; ws["B1"] = "STYLE"
    ws["A2"] = "1063"; ws["B2"] = "DWJE"
    ws["A3"] = "1064"; ws["B3"] = "DWJF"
    # Stage band with mostly non-date values
    ws["C5"] = "Pre-Prod"
    ws["D5"] = "L/D send"; ws["E5"] = "Fit send"
    ws["D6"] = "pending"; ws["E6"] = datetime(2026, 3, 5)
    ws["D7"] = "pending"; ws["E7"] = "tbd"
```

```json
{
  "fixture": "stage_band_low_date_density",
  "description": "Stage band columns mostly contain string placeholders, not dates.",
  "layer_expectations": {
    "flow": {
      "plan_statistics_warnings_must_contain": ["date_band_density"]
    }
  },
  "failure_expectations": {
    "category": "data_anomaly",
    "expected_warning_check": "date_band_density",
    "graceful_degradation": true
  }
}
```

- [ ] **Step 4: Smoke-test the new fixtures load**

```python
# tests/fixtures/test_fixture_pool_phase_b3.py
from tests.fixtures.case import fixture_case


@fixture_case("workbook_only_title_row", "tabular_corrupt_no_identity_col", "stage_band_low_date_density")
def test_phase_b3_fixtures_load(fixture):
    assert fixture.is_failure_case()
    assert fixture.failure_expectations()["graceful_degradation"] is True
```

Run:
```
.venv/Scripts/python.exe -m pytest tests/fixtures/test_fixture_pool_phase_b3.py -q
```
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/builders/workbook_only_title_row.py tests/fixtures/builders/tabular_corrupt_no_identity_col.py tests/fixtures/builders/stage_band_low_date_density.py tests/fixtures/expected/workbook_only_title_row.json tests/fixtures/expected/tabular_corrupt_no_identity_col.json tests/fixtures/expected/stage_band_low_date_density.json tests/fixtures/test_fixture_pool_phase_b3.py
git commit -m "test(fixtures): failure anchors — input validation, planner ambiguity, data anomaly"
```

---

### Task 9: Failure anchors — plan invariant + apply mismatch + agent failure

Three fixtures:
- `plan_invariant_dangling_anchor` (synthetic plan — uses `build_plan()`)
- `apply_name_map_missing_required`
- `agent_returns_invalid_json`

- [ ] **Step 1: Author `plan_invariant_dangling_anchor` (synthetic plan)**

```python
# tests/fixtures/builders/plan_invariant_dangling_anchor.py
"""Synthetic SheetPlan with a CHILD row pointing at a non-existent ANCHOR.

Bypasses the planner — this is corrupt input fed directly into the validator
to confirm Tier 1 catches it.
"""
from app.models.artifacts import SheetPlan, RowSpec
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope


def build_plan() -> SheetPlan:
    return SheetPlan(
        sheet="S",
        pli_mode=PliMode.ROW_PER_PLI,
        identity_column="A",
        header_rows=[1],
        rows=[
            RowSpec(idx=2, role=RowRole.ANCHOR, group_id=0),
            RowSpec(idx=3, role=RowRole.CHILD, anchor_idx=99, group_id=0),
        ],
        stage_scope=StageScope.SHEET_LEVEL,
        confidence=1.0,
    )
```

```json
{
  "fixture": "plan_invariant_dangling_anchor",
  "description": "SheetPlan with CHILD pointing at non-existent ANCHOR — corrupt graph.",
  "layer_expectations": {
    "flow": {
      "plan_invariants_must_contain_error": "reference_integrity"
    }
  },
  "failure_expectations": {
    "category": "plan_invariant",
    "expected_invariant_violation": "reference_integrity",
    "expected_severity": "error"
  }
}
```

- [ ] **Step 2: Author `apply_name_map_missing_required`**

```python
# tests/fixtures/builders/apply_name_map_missing_required.py
"""A normal tabular sheet, but the e2e test will pass an empty name_map so
apply_plan can't resolve labels → canonical fields.

Tests apply_plan's behavior when CanonicalNameMap is missing entries.
"""
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "IO NO"; ws["B1"] = "STYLE"
    ws["A2"] = "1063"; ws["B2"] = "DWJE"
```

```json
{
  "fixture": "apply_name_map_missing_required",
  "description": "Tabular sheet processed with an empty CanonicalNameMap.",
  "layer_expectations": {
    "e2e": {
      "fake_llm_responses": {
        "SheetClassifierOutput": {"relevant_sheets": ["S"]},
        "CanonicalNameMap": {"field_labels": {}, "stage_names": {}},
        "LayoutHints": {},
        "PlanVerdict": {"verdict": "looks_correct"}
      },
      "pli_count_min": 0,
      "pli_count_max": 1
    }
  },
  "failure_expectations": {
    "category": "apply_mismatch",
    "graceful_degradation": true,
    "io_number_field_must_be_none_or_unset": true
  }
}
```

- [ ] **Step 3: Author `agent_returns_invalid_json`**

```python
# tests/fixtures/builders/agent_returns_invalid_json.py
"""A normal tabular sheet. The agent test will pass a FakeLLM that raises
ValidationError when asked for CanonicalNameMap, simulating an agent
returning unparseable output.
"""
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "IO NO"
    ws["A2"] = "1063"
```

```json
{
  "fixture": "agent_returns_invalid_json",
  "description": "Tabular sheet with a FakeLLM that simulates agent failure for FieldNamer.",
  "layer_expectations": {
    "agent": {
      "field_namer": {
        "canned_response_invalid": true,
        "expected_fallback_name_map": {"field_labels": {}, "stage_names": {}}
      }
    }
  },
  "failure_expectations": {
    "category": "agent_failure",
    "graceful_degradation": true
  }
}
```

- [ ] **Step 4: Smoke-test the new fixtures load**

```python
# tests/fixtures/test_fixture_pool_phase_b4.py
from tests.fixtures.case import fixture_case
from app.models.artifacts import SheetPlan


@fixture_case("plan_invariant_dangling_anchor")
def test_synthetic_plan_loads(fixture):
    # synthetic plan fixture has no xlsx_path
    assert fixture.xlsx_path is None
    assert fixture.ctx is None
    # We can't access the SheetPlan through FixtureCase directly; tests do
    # that by importing the builder module. Just confirm fixture loads.
    assert fixture.is_failure_case()


@fixture_case("apply_name_map_missing_required", "agent_returns_invalid_json")
def test_remaining_failure_fixtures_load(fixture):
    assert fixture.is_failure_case()
```

Run:
```
.venv/Scripts/python.exe -m pytest tests/fixtures/test_fixture_pool_phase_b4.py -q
```
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/builders/plan_invariant_dangling_anchor.py tests/fixtures/builders/apply_name_map_missing_required.py tests/fixtures/builders/agent_returns_invalid_json.py tests/fixtures/expected/plan_invariant_dangling_anchor.json tests/fixtures/expected/apply_name_map_missing_required.json tests/fixtures/expected/agent_returns_invalid_json.json tests/fixtures/test_fixture_pool_phase_b4.py
git commit -m "test(fixtures): failure anchors — plan invariant, apply mismatch, agent failure"
```

---

## Phase C — Reorganize existing tests by simple moves

### Task 10: Move regression + live integration tests to `tests/live/`

**Files:**
- Move: `tests/regression/test_christian_berg.py` → `tests/live/test_christian_berg.py`
- Move: `tests/regression/test_new_job_tna.py` → `tests/live/test_new_job_tna.py`
- Move: `tests/integration/test_e2e_live.py` → `tests/live/test_dataset_acceptance.py`
- Delete: `tests/regression/` directory (after moves)

- [ ] **Step 1: Move files via git mv**

```bash
git mv tests/regression/test_christian_berg.py tests/live/test_christian_berg.py
git mv tests/regression/test_new_job_tna.py tests/live/test_new_job_tna.py
git mv tests/integration/test_e2e_live.py tests/live/test_dataset_acceptance.py
git rm tests/regression/__init__.py
rmdir tests/regression
```

- [ ] **Step 2: Verify pytest still discovers them**

```
.venv/Scripts/python.exe -m pytest tests/live --collect-only -q
```
Expected: shows 3+ collected tests with `live` markers.

- [ ] **Step 3: Verify nothing else broke**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```
Expected: 154+ passed.

- [ ] **Step 4: Commit**

```bash
git commit -m "test(reorg): move regression + e2e live tests into tests/live/"
```

---

### Task 11: Move acceptance test + repositories tests

**Files:**
- Move: `tests/integration/test_acceptance_extensibility.py` → `tests/unit/structure/test_layout.py`
- Move: `tests/repositories/*` → `tests/unit/repositories/`
- Delete: `tests/integration/` directory (after moves, if empty)

- [ ] **Step 1: Move the acceptance test**

```bash
git mv tests/integration/test_acceptance_extensibility.py tests/unit/structure/test_layout.py
git rm tests/integration/__init__.py
rmdir tests/integration 2>/dev/null || true
```

- [ ] **Step 2: Check what's still in `tests/integration/`**

```bash
ls tests/integration 2>&1
```
If only `test_extraction_pipeline.py` remains, leave it for Task 12 to migrate.
If empty, the rmdir above succeeded.

- [ ] **Step 3: Move repositories tests**

```bash
mkdir -p tests/unit/repositories
git mv tests/repositories/__init__.py tests/unit/repositories/__init__.py 2>/dev/null || touch tests/unit/repositories/__init__.py
for f in tests/repositories/test_*.py; do
  name=$(basename $f)
  git mv $f tests/unit/repositories/$name
done
rmdir tests/repositories 2>/dev/null || true
```

- [ ] **Step 4: Verify suite still passes**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```
Expected: 154+ passed, no regressions.

- [ ] **Step 5: Commit**

```bash
git commit -m "test(reorg): move acceptance + repositories tests into tests/unit/"
```

---

## Phase D — Rewrite composite tests as flow tier

### Task 12: Rewrite `test_apply_plan_row_per_pli` using fixtures

**Files:**
- Create: `tests/flow/test_apply_plan_row_per_pli.py`
- Delete: `tests/unit/applier/test_apply_plan_row_per_pli.py`
- Also: rewrite or migrate `tests/integration/test_extraction_pipeline.py` into a new e2e file (next task can pick it up, or do it here)

- [ ] **Step 1: Write the new fixture-driven flow test**

```python
# tests/flow/test_apply_plan_row_per_pli.py
"""Flow test: SheetRowPlanner + apply_plan for ROW_PER_PLI fixtures."""
from app.services.applier.apply_plan import apply_plan
from app.services.planner.plan import SheetRowPlanner
from app.models.artifacts import CanonicalNameMap
from tests.fixtures.case import fixture_case


@fixture_case("tabular_simple", "tabular_with_totals", "row_per_pli_with_merges")
def test_apply_plan_row_per_pli_emits_expected_plis(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    name_map = CanonicalNameMap(
        **fixture.expectations("e2e")["fake_llm_responses"]["CanonicalNameMap"]
    )
    plis = apply_plan(fixture.ctx, plan, name_map)
    e2e = fixture.expectations("e2e")
    assert len(plis) == e2e["pli_count"]
    expected_ios = e2e["io_numbers"]
    assert [p.io_number for p in plis] == expected_ios
```

- [ ] **Step 2: Run the new test**

```
.venv/Scripts/python.exe -m pytest tests/flow/test_apply_plan_row_per_pli.py -q
```
Expected: `3 passed` (one per fixture).

- [ ] **Step 3: Delete the old test**

```bash
git rm tests/unit/applier/test_apply_plan_row_per_pli.py
```

- [ ] **Step 4: Verify no regression**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```
Expected: count drops by 1 (the old test was 1 test method) and increases by 3 (new parametrized). Net +2 or stable.

- [ ] **Step 5: Commit**

```bash
git add tests/flow/test_apply_plan_row_per_pli.py
git commit -m "test(flow): rewrite apply_plan row_per_pli using fixtures"
```

---

### Task 13: Rewrite `test_apply_plan_sheet_is_pli` using fixtures

**Files:**
- Create: `tests/flow/test_apply_plan_sheet_is_pli.py`
- Delete: `tests/unit/applier/test_apply_plan_sheet_is_pli.py`

- [ ] **Step 1: Write the new test**

```python
# tests/flow/test_apply_plan_sheet_is_pli.py
"""Flow test: SheetRowPlanner + apply_plan for SHEET_IS_PLI fixtures."""
from app.services.applier.apply_plan import apply_plan
from app.services.planner.plan import SheetRowPlanner
from app.models.artifacts import CanonicalNameMap
from tests.fixtures.case import fixture_case


@fixture_case("sheet_per_pli_clean")
def test_apply_plan_sheet_is_pli_one_per_sheet(fixture):
    e2e = fixture.expectations("e2e")
    name_map = CanonicalNameMap(**e2e["fake_llm_responses"]["CanonicalNameMap"])
    plis_total = []
    for sheet in fixture.sheets:
        plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=sheet)["plan"]
        plis = apply_plan(fixture.ctx, plan, name_map)
        plis_total.extend(plis)
    assert len(plis_total) == e2e["pli_count"]
    assert [p.io_number for p in plis_total] == e2e["io_numbers"]
```

- [ ] **Step 2: Run**

```
.venv/Scripts/python.exe -m pytest tests/flow/test_apply_plan_sheet_is_pli.py -q
```
Expected: `1 passed`.

- [ ] **Step 3: Delete the old**

```bash
git rm tests/unit/applier/test_apply_plan_sheet_is_pli.py
```

- [ ] **Step 4: Verify**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```

- [ ] **Step 5: Commit**

```bash
git add tests/flow/test_apply_plan_sheet_is_pli.py
git commit -m "test(flow): rewrite apply_plan sheet_is_pli using fixtures"
```

---

### Task 14: Rewrite `test_apply_plan_section_per_pli` using fixtures

**Files:**
- Create: `tests/flow/test_apply_plan_section_per_pli.py`
- Delete: `tests/unit/applier/test_apply_plan_section_per_pli.py`

- [ ] **Step 1: Write the new test**

```python
# tests/flow/test_apply_plan_section_per_pli.py
"""Flow test: apply_plan SECTION_PER_PLI mode via fixtures.

The section_per_pli_two_blocks fixture might be classified as ROW_PER_PLI
by the planner (heuristic isn't strict). The test accepts either path and
asserts on PLI count + identity instead of mode.
"""
from app.services.applier.apply_plan import apply_plan
from app.services.planner.plan import SheetRowPlanner
from app.models.artifacts import CanonicalNameMap
from tests.fixtures.case import fixture_case


@fixture_case("section_per_pli_two_blocks")
def test_apply_plan_section_per_pli_emits_two_plis(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    e2e = fixture.expectations("e2e")
    name_map = CanonicalNameMap(**e2e["fake_llm_responses"]["CanonicalNameMap"])
    plis = apply_plan(fixture.ctx, plan, name_map)
    assert len(plis) == e2e["pli_count"]
    assert sorted(p.io_number for p in plis) == sorted(e2e["io_numbers"])
```

- [ ] **Step 2: Run, delete old, verify, commit**

```
.venv/Scripts/python.exe -m pytest tests/flow/test_apply_plan_section_per_pli.py -q
```
Expected: `1 passed`.

```bash
git rm tests/unit/applier/test_apply_plan_section_per_pli.py
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
git add tests/flow/test_apply_plan_section_per_pli.py
git commit -m "test(flow): rewrite apply_plan section_per_pli using fixtures"
```

---

### Task 15: Rewrite `test_plan.py` as `test_planner_pipeline.py`

**Files:**
- Create: `tests/flow/test_planner_pipeline.py`
- Delete: `tests/unit/planner/test_plan.py`

- [ ] **Step 1: Write the new test**

```python
# tests/flow/test_planner_pipeline.py
"""Flow test: SheetRowPlanner emits expected SheetPlan per fixture."""
from app.services.planner.plan import SheetRowPlanner
from app.enums.row_role import RowRole
from tests.fixtures.case import fixture_case


@fixture_case(
    "tabular_simple", "tabular_with_totals", "tabular_repeat_header",
    "sheet_per_pli_clean", "row_per_pli_with_merges",
)
def test_planner_emits_expected_plan(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    flow = fixture.expectations("flow")
    if "pli_mode" in flow:
        assert plan.pli_mode.value == flow["pli_mode"]
    if "identity_column" in flow:
        assert plan.identity_column == flow["identity_column"]
    if "anchor_count" in flow:
        anchors = [r for r in plan.rows if r.role is RowRole.ANCHOR]
        assert len(anchors) == flow["anchor_count"]
    if "child_count" in flow:
        children = [r for r in plan.rows if r.role is RowRole.CHILD]
        assert len(children) == flow["child_count"]
    if "kv_anchor_count_per_sheet" in flow:
        assert len(plan.kv_anchors) == flow["kv_anchor_count_per_sheet"][0]
    if "stage_band_count_per_sheet" in flow:
        assert len(plan.stage_bands) == flow["stage_band_count_per_sheet"][0]
    if "header_rows" in flow:
        assert plan.header_rows == flow["header_rows"]
```

- [ ] **Step 2: Run**

```
.venv/Scripts/python.exe -m pytest tests/flow/test_planner_pipeline.py -q
```
Expected: 5 passed.

- [ ] **Step 3: Delete the old test**

```bash
git rm tests/unit/planner/test_plan.py
```

- [ ] **Step 4: Verify**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```

- [ ] **Step 5: Commit**

```bash
git add tests/flow/test_planner_pipeline.py
git commit -m "test(flow): rewrite SheetRowPlanner test using fixture pool"
```

---

## Phase E — Migrate agent tests to behaviour tests with FakeLLM

### Task 16: Agent test — `SheetClassifier`

**Files:**
- Create: `tests/agent/test_sheet_classifier.py`
- Delete: `tests/unit/agents/test_sheet_classifier.py`

- [ ] **Step 1: Write the new behaviour test**

```python
# tests/agent/test_sheet_classifier.py
"""Agent test: SheetClassifier behaviour under canned LLM responses."""
from app.services.agents.sheet_classifier import SheetClassifier
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
import app.repositories.workbook_tools.survey  # noqa: F401 — register tools
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("tabular_simple")
def test_sheet_classifier_returns_canned_relevant_sheets(fixture):
    e2e = fixture.expectations("e2e")
    fake_responses = e2e["fake_llm_responses"]
    llm = FakeLLM(canned={"SheetClassifierOutput": fake_responses["SheetClassifierOutput"]})
    summary = TOOL_REGISTRY.get("workbook_summary")(fixture.ctx)
    out = SheetClassifier(llm=llm).run(workbook_ctx=fixture.ctx, workbook_summary=summary)
    assert out["relevant_sheets"] == fake_responses["SheetClassifierOutput"]["relevant_sheets"]
```

- [ ] **Step 2: Run**

```
.venv/Scripts/python.exe -m pytest tests/agent/test_sheet_classifier.py -q
```
Expected: `1 passed`.

- [ ] **Step 3: Delete the old smoke test**

```bash
git rm tests/unit/agents/test_sheet_classifier.py
```

- [ ] **Step 4: Verify + commit**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
git add tests/agent/test_sheet_classifier.py
git commit -m "test(agent): SheetClassifier behaviour test with FakeLLM"
```

---

### Task 17: Agent test — `LayoutHinter`

**Files:**
- Create: `tests/agent/test_layout_hinter.py`
- Delete: `tests/unit/agents/test_layout_hinter.py`

- [ ] **Step 1: Write**

```python
# tests/agent/test_layout_hinter.py
"""Agent test: LayoutHinter under canned response."""
from app.services.agents.layout_hinter import LayoutHinter
from app.services.planner.surveyor import survey_sheet
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("tabular_corrupt_no_identity_col")
def test_layout_hinter_returns_canned_hints(fixture):
    e2e = fixture.expectations("e2e")
    canned = e2e["fake_llm_responses"]["LayoutHints"]
    llm = FakeLLM(canned={"LayoutHints": canned})
    signals = survey_sheet(fixture.ctx, fixture.sheet)
    out = LayoutHinter(llm=llm).run(
        workbook_ctx=fixture.ctx, sheet=fixture.sheet, signals=signals,
    )
    assert out["hints"].identity_column_suggestion == canned.get("identity_column_suggestion")
```

- [ ] **Step 2: Run, delete old, verify, commit**

```
.venv/Scripts/python.exe -m pytest tests/agent/test_layout_hinter.py -q
git rm tests/unit/agents/test_layout_hinter.py
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
git add tests/agent/test_layout_hinter.py
git commit -m "test(agent): LayoutHinter behaviour test with FakeLLM"
```

---

### Task 18: Agent test — `PlanReviewer`

**Files:**
- Create: `tests/agent/test_plan_reviewer.py`
- Delete: `tests/unit/agents/test_plan_reviewer.py`

- [ ] **Step 1: Write**

```python
# tests/agent/test_plan_reviewer.py
"""Agent test: PlanReviewer judges a SheetPlan."""
from app.services.agents.plan_reviewer import PlanReviewer
from app.services.planner.plan import SheetRowPlanner
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("tabular_simple")
def test_plan_reviewer_returns_canned_verdict(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    canned = fixture.expectations("e2e")["fake_llm_responses"]["PlanVerdict"]
    llm = FakeLLM(canned={"PlanVerdict": canned})
    out = PlanReviewer(llm=llm).run(workbook_ctx=fixture.ctx, plan=plan, findings=[])
    assert out["verdict"].verdict == canned["verdict"]
```

- [ ] **Step 2: Run, delete old, verify, commit**

```
.venv/Scripts/python.exe -m pytest tests/agent/test_plan_reviewer.py -q
git rm tests/unit/agents/test_plan_reviewer.py
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
git add tests/agent/test_plan_reviewer.py
git commit -m "test(agent): PlanReviewer behaviour test with FakeLLM"
```

---

### Task 19: Agent test — `FieldNamer`

**Files:**
- Create: `tests/agent/test_field_namer.py`
- Delete: `tests/unit/agents/test_field_namer.py`

- [ ] **Step 1: Write**

```python
# tests/agent/test_field_namer.py
"""Agent test: FieldNamer maps labels to canonical names."""
from app.services.agents.field_namer import FieldNamer
from app.services.planner.plan import SheetRowPlanner
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("tabular_simple")
def test_field_namer_returns_canned_canonical_map(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    canned = fixture.expectations("e2e")["fake_llm_responses"]["CanonicalNameMap"]
    llm = FakeLLM(canned={"CanonicalNameMap": canned})
    out = FieldNamer(llm=llm).run(workbook_ctx=fixture.ctx, plan=plan)
    assert out["name_map"].field_labels == canned["field_labels"]
```

- [ ] **Step 2: Run, delete old, verify, commit**

```
.venv/Scripts/python.exe -m pytest tests/agent/test_field_namer.py -q
git rm tests/unit/agents/test_field_namer.py
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
git add tests/agent/test_field_namer.py
git commit -m "test(agent): FieldNamer behaviour test with FakeLLM"
```

---

### Task 20: Migrate `test_extraction_pipeline.py` into `tests/e2e/`

**Files:**
- Create: `tests/e2e/test_extract_against_fixtures.py`
- Delete: `tests/integration/test_extraction_pipeline.py`
- Delete: `tests/integration/__init__.py` (if directory now empty)

- [ ] **Step 1: Write the new fixture-driven e2e test**

```python
# tests/e2e/test_extract_against_fixtures.py
"""End-to-end test: full extract() pipeline with FakeLLM against fixtures."""
from app.services.extraction import extract
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case(
    "tabular_simple", "tabular_with_totals", "row_per_pli_with_merges",
    "sheet_per_pli_clean",
)
def test_extract_emits_expected_plis(fixture):
    llm = FakeLLM(canned=fixture.fake_llm_responses())
    result = extract(fixture.xlsx_path, llm=llm)
    e2e = fixture.expectations("e2e")
    assert len(result.plis) == e2e["pli_count"]
    expected_ios = e2e["io_numbers"]
    actual_ios = [p.io_number for p in result.plis]
    assert sorted(actual_ios) == sorted(expected_ios)
```

- [ ] **Step 2: Run**

```
.venv/Scripts/python.exe -m pytest tests/e2e/test_extract_against_fixtures.py -q
```
Expected: `4 passed`.

- [ ] **Step 3: Delete the old test + empty directory**

```bash
git rm tests/integration/test_extraction_pipeline.py
git rm tests/integration/__init__.py 2>/dev/null || true
rmdir tests/integration 2>/dev/null || true
```

- [ ] **Step 4: Verify + commit**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
git add tests/e2e/test_extract_against_fixtures.py
git commit -m "test(e2e): fixture-driven extract() test, replaces test_extraction_pipeline"
```

---

## Phase F — Failure-case tests

### Task 21: Failure test — input validation (e2e tier)

**Files:**
- Create: `tests/e2e/test_failure_input_validation.py`

- [ ] **Step 1: Write**

```python
# tests/e2e/test_failure_input_validation.py
"""E2E failure test: input validation — title-only workbook returns empty plis without crashing."""
from app.services.extraction import extract
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("workbook_only_title_row")
def test_extract_handles_title_only_workbook(fixture):
    llm = FakeLLM(canned=fixture.fake_llm_responses())
    result = extract(fixture.xlsx_path, llm=llm)
    failure = fixture.failure_expectations()
    assert failure["graceful_degradation"] is True
    e2e = fixture.expectations("e2e")
    assert len(result.plis) == e2e["pli_count"]
    # Must not raise; pipeline returns a valid ExtractionResult.
    assert result.source_file is not None
```

- [ ] **Step 2: Run + commit**

```
.venv/Scripts/python.exe -m pytest tests/e2e/test_failure_input_validation.py -q
git add tests/e2e/test_failure_input_validation.py
git commit -m "test(e2e/failure): input validation graceful degradation"
```

---

### Task 22: Failure test — planner ambiguity (flow tier)

**Files:**
- Create: `tests/flow/test_failure_planner_ambiguity.py`

- [ ] **Step 1: Write**

```python
# tests/flow/test_failure_planner_ambiguity.py
"""Flow failure test: planner ambiguity — no identity column candidates."""
from app.services.planner.plan import SheetRowPlanner
from app.services.validation.plan_statistics import validate_statistics
from tests.fixtures.case import fixture_case


@fixture_case("tabular_corrupt_no_identity_col")
def test_planner_ambiguity_flags_pli_count_sanity(fixture):
    assert fixture.is_failure_case()
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    findings = validate_statistics(fixture.ctx, plan)
    warnings = [f.check for f in findings]
    expected_check = fixture.failure_expectations()["expected_warning_check"]
    assert expected_check in warnings
```

- [ ] **Step 2: Run + commit**

```
.venv/Scripts/python.exe -m pytest tests/flow/test_failure_planner_ambiguity.py -q
git add tests/flow/test_failure_planner_ambiguity.py
git commit -m "test(flow/failure): planner ambiguity flags pli_count_sanity"
```

---

### Task 23: Failure test — plan invariant violation (flow tier)

**Files:**
- Create: `tests/flow/test_failure_plan_invariants.py`

- [ ] **Step 1: Write**

```python
# tests/flow/test_failure_plan_invariants.py
"""Flow failure test: synthetic SheetPlan with dangling anchor_idx triggers
reference_integrity ERROR from validate_invariants."""
import importlib
from app.services.validation.plan_invariants import validate_invariants
from app.enums.validation_severity import ValidationSeverity
from tests.fixtures.case import fixture_case


@fixture_case("plan_invariant_dangling_anchor")
def test_plan_invariant_detects_dangling_anchor(fixture):
    # Synthetic-plan fixtures expose build_plan(); load the module to call it.
    mod = importlib.import_module(f"tests.fixtures.builders.{fixture.name}")
    plan = mod.build_plan()
    findings = validate_invariants(plan)
    expected_violation = fixture.failure_expectations()["expected_invariant_violation"]
    errors = [f for f in findings if f.severity == ValidationSeverity.ERROR]
    assert any(f.check == expected_violation for f in errors)
```

- [ ] **Step 2: Run + commit**

```
.venv/Scripts/python.exe -m pytest tests/flow/test_failure_plan_invariants.py -q
git add tests/flow/test_failure_plan_invariants.py
git commit -m "test(flow/failure): plan_invariants detects dangling anchor_idx"
```

---

### Task 24: Failure test — apply mismatch (e2e tier)

**Files:**
- Create: `tests/e2e/test_failure_apply_mismatches.py`

- [ ] **Step 1: Write**

```python
# tests/e2e/test_failure_apply_mismatches.py
"""E2E failure test: apply_plan handles empty CanonicalNameMap gracefully.

With an empty name_map, fields can't be resolved to canonical names. The
pipeline should still produce a (mostly-empty) PLI without crashing.
"""
from app.services.extraction import extract
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("apply_name_map_missing_required")
def test_extract_with_empty_name_map_degrades_gracefully(fixture):
    llm = FakeLLM(canned=fixture.fake_llm_responses())
    result = extract(fixture.xlsx_path, llm=llm)
    e2e = fixture.expectations("e2e")
    assert e2e["pli_count_min"] <= len(result.plis) <= e2e["pli_count_max"]
    # With empty name_map, io_number won't be set on any PLI.
    for pli in result.plis:
        assert pli.io_number is None or pli.io_number == ""
```

- [ ] **Step 2: Run + commit**

```
.venv/Scripts/python.exe -m pytest tests/e2e/test_failure_apply_mismatches.py -q
git add tests/e2e/test_failure_apply_mismatches.py
git commit -m "test(e2e/failure): apply_plan degrades gracefully with empty name_map"
```

---

### Task 25: Failure test — agent degradation (agent tier)

**Files:**
- Create: `tests/agent/test_failure_agent_degradation.py`

- [ ] **Step 1: Write**

```python
# tests/agent/test_failure_agent_degradation.py
"""Agent failure test: FieldNamer falls back to empty CanonicalNameMap when
the LLM raises during respond.

FakeLLM raising mimics an agent returning unparseable output.
"""
import pytest
from app.services.agents.field_namer import FieldNamer
from app.services.planner.plan import SheetRowPlanner
from tests.fixtures.case import fixture_case


class _RaisingLLM:
    def complete_with_schema(self, system, user, output_schema, tool_name=None):
        raise RuntimeError("simulated LLM failure")


@fixture_case("agent_returns_invalid_json")
def test_field_namer_falls_back_when_llm_fails(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    fb = FieldNamer(llm=_RaisingLLM()).run(workbook_ctx=fixture.ctx, plan=plan)
    expected = fixture.expectations("agent")["field_namer"]["expected_fallback_name_map"]
    assert fb["name_map"].field_labels == expected["field_labels"]
    assert fb["name_map"].stage_names == expected["stage_names"]
```

- [ ] **Step 2: Run + commit**

```
.venv/Scripts/python.exe -m pytest tests/agent/test_failure_agent_degradation.py -q
git add tests/agent/test_failure_agent_degradation.py
git commit -m "test(agent/failure): FieldNamer falls back to empty name_map on LLM failure"
```

---

### Task 26: Failure test — data anomaly (flow tier)

**Files:**
- Create: `tests/flow/test_failure_data_anomalies.py`

- [ ] **Step 1: Write**

```python
# tests/flow/test_failure_data_anomalies.py
"""Flow failure test: stage band with mostly non-date cells triggers
date_band_density warning from validate_statistics."""
from app.services.planner.plan import SheetRowPlanner
from app.services.validation.plan_statistics import validate_statistics
from tests.fixtures.case import fixture_case


@fixture_case("stage_band_low_date_density")
def test_low_date_density_flags_warning(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    findings = validate_statistics(fixture.ctx, plan)
    expected_check = fixture.failure_expectations()["expected_warning_check"]
    checks = [f.check for f in findings]
    assert expected_check in checks
```

- [ ] **Step 2: Run + commit**

```
.venv/Scripts/python.exe -m pytest tests/flow/test_failure_data_anomalies.py -q
git add tests/flow/test_failure_data_anomalies.py
git commit -m "test(flow/failure): stage band low date density triggers warning"
```

---

## Phase G — Write the rules

### Task 27: Author `docs/TESTING.md`

**Files:**
- Create: `docs/TESTING.md`
- Modify: `docs/SPEC.md` (add a § Testing strategy section that links to `docs/TESTING.md`)

- [ ] **Step 1: Write `docs/TESTING.md`**

Full content:

```markdown
# Testing conventions

How to write tests for the TNA service. Read top-to-bottom once; refer back
when adding new tests.

## 1. Pick the tier first

| Tier | When to use |
|---|---|
| `tests/unit/` | One function, no fixture needed. Inline synthetic input, direct assertion. |
| `tests/flow/` | 2+ deterministic functions chained — e.g. `survey → row_classifier → segmenter`. Always fixture-driven. |
| `tests/agent/` | Single LLM agent, `FakeLLM` stub. Always fixture-driven. |
| `tests/e2e/` | Full `extract()` pipeline, `FakeLLM` stub. Always fixture-driven. |
| `tests/live/` | Real Anthropic API, real `dataset/*.xlsx`. Marked `@pytest.mark.live`. |

If a test exercises one function in one module → `unit/`. If it chains
multiple modules → `flow/`. If it invokes an LLM agent → `agent/` or `e2e/`.
If it talks to the real API → `live/`.

## 2. One fixture = one builder + one expected.json

To add a new test scenario:
1. Create `tests/fixtures/builders/<name>.py` with a `build(wb)` function.
2. Create `tests/fixtures/expected/<name>.json` with the assertions.
3. Use `@fixture_case("<name>")` in your test. No file paths in test code.

Builder names use snake_case and describe the scenario, not the test:
`tabular_with_totals.py` ✓, `test_christian_berg.py` ✗.

For synthetic-plan fixtures (no xlsx needed — e.g. plan invariant tests),
the builder exports `build_plan() -> SheetPlan` instead of `build(wb)`.

## 3. Fixtures stay minimal

Build only what the test needs. A fixture for `sheet_is_pli` mode detection
needs 3 sheets and 2 KV labels per sheet — not a full TNA replica. Smaller
fixtures fail faster and isolate bugs better.

## 4. Expected.json is keyed by tier

```json
{
  "fixture": "<name>",
  "description": "<one-line>",
  "layer_expectations": {
    "flow": { ... },
    "agent": { ... },
    "e2e": { ... },
    "live": { ... }
  },
  "failure_expectations": null
}
```

A fixture only needs the tier sections it'll be used in. Asking for a
missing tier in a test raises a clear AssertionError.

## 5. Failure cases follow the same shape

A failure-case fixture has `failure_expectations` populated. Tests assert
on degradation behaviour — Warnings emitted, PLIs dropped, validators
flagged — not on raised exceptions, unless the contract is "raise."

| Failure category | Builder lives at | Assertion target |
|---|---|---|
| Input validation | `builders/workbook_<scenario>.py` | `result.warnings`, `pli_count == 0` |
| Planner ambiguity | `builders/tabular_corrupt_<scenario>.py` | `plan_statistics_warnings` contains expected check |
| Plan invariant | `builders/plan_invariant_<scenario>.py` (synthetic — `build_plan()`) | `validate_invariants` returns ERROR |
| Apply mismatch | `builders/apply_<scenario>.py` | typed exception caught by orchestrator, warning recorded |
| Agent failure | `builders/agent_<scenario>.py` | pipeline continues, det classification wins |
| Data anomaly | `builders/<feature>_low_<signal>.py` | Tier 2 warning emitted |

## 6. Agent tests use canned LLM responses

Each agent test:
1. Loads a fixture (input artifact).
2. Builds a `FakeLLM` with canned responses from `fixture.expectations("agent")`.
3. Runs the agent.
4. Asserts on the agent's processed output, not the raw LLM string.

Don't call real LLM APIs from `agent/` tests. Use `live/` for that.

## 7. Use `@fixture_case`, never `register_workbook` directly

The decorator handles cache cleanup, materialization, and ctx wiring. Direct
`register_workbook` calls in tests bypass isolation guarantees.

```python
# good
@fixture_case("tabular_simple")
def test_planner(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    assert plan.pli_mode.value == fixture.expectations("flow")["pli_mode"]
```

Exception: `tests/unit/` may build small inline workbooks. The decorator is
only required for tiers that share fixtures.

## 8. Run pattern

| Command | What it runs |
|---|---|
| `pytest tests -q` | Everything except `live/` (default deselects `@pytest.mark.live`). |
| `pytest tests -m live -q` | Only live tests — needs `ANTHROPIC_API_KEY` + real dataset. |
| `pytest tests/flow -q` | Just the flow tier. |
| `pytest tests/flow -q -k "with_totals"` | Filter by scenario substring. |
| `pytest tests --collect-only -q` | List tests; useful to confirm placement. |

## Anti-patterns to avoid

- **Don't put a fixture file under `tests/<tier>/`**. Fixtures live in
  `tests/fixtures/`. Tiers contain test code only.
- **Don't share state between tests via module globals.** Use `FixtureCase`.
- **Don't use `scope="module"` or `scope="session"` on workbook fixtures.**
  Function-scope is the contract.
- **Don't write tests that pass against the real LLM but fail with FakeLLM.**
  If e2e and live disagree, the e2e canned response is wrong — update it.
- **Don't commit large xlsx files outside `dataset/`.** Anything in
  `tests/fixtures/` should be a Python builder.
- **Don't reference plan/task numbers in tests.** Names describe behaviour.

## Adding a new layout family — the cookbook

1. Decide what makes it distinct. Write a one-line description.
2. Author `tests/fixtures/builders/<name>.py` — minimal workbook that
   exhibits the feature.
3. Author `tests/fixtures/expected/<name>.json` with `layer_expectations`
   for whichever tiers it'll be tested in.
4. Add the fixture name to the `@fixture_case(...)` of any existing test
   that should now cover this family.
5. If the family exposes a NEW behaviour, write a new test that names this
   fixture explicitly.
```

- [ ] **Step 2: Update `docs/SPEC.md` to link to TESTING.md**

Open `docs/SPEC.md`, find the existing § Testing strategy section. Add at the end:

```markdown
For the full testing conventions — tiers, fixtures, failure-case patterns,
and the cookbook for adding new layouts — see [`docs/TESTING.md`](TESTING.md).
```

- [ ] **Step 3: Commit**

```bash
git add docs/TESTING.md docs/SPEC.md
git commit -m "docs: TESTING.md conventions; SPEC links to it"
```

---

## Phase H — Cleanup & verify

### Task 28: Full suite + collect-only verification

- [ ] **Step 1: Run full non-live suite**

```
.venv/Scripts/python.exe -m pytest tests -q -m "not live"
```
Expected: 154+ passed. Capture the exact number.

- [ ] **Step 2: Run collect-only and audit tier placement**

```
.venv/Scripts/python.exe -m pytest tests --collect-only -q -m "not live"
```

Visually confirm:
- No tests remain in `tests/regression/`, `tests/integration/`, or `tests/repositories/` (these dirs should not exist).
- Each migrated test landed in its expected tier (`tests/flow/`, `tests/agent/`, `tests/e2e/`, `tests/live/`).

- [ ] **Step 3: Confirm no xlsx binaries committed**

```bash
git ls-files tests/fixtures/ | grep -E '\.xlsx$' && echo "FAIL: xlsx files committed!" || echo "OK: no xlsx binaries"
```
Expected: `OK: no xlsx binaries`.

- [ ] **Step 4: Flip design doc Status**

Open `docs/superpowers/specs/2026-05-13-test-strategy-design.md`. Change:

```
**Status:** Approved, ready for implementation plan
```

to:

```
**Status:** Implemented
```

- [ ] **Step 5: Optional live run (only if `ANTHROPIC_API_KEY` is set + dataset present)**

```
.venv/Scripts/python.exe -m pytest tests -m live -q
```

Expected: live tests pass (CHRISTIAN BERG, new job-TNA, dataset acceptance).

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-05-13-test-strategy-design.md
git commit -m "docs: mark test-strategy spec as Implemented"
```

---

## Self-review checklist (run after all tasks complete)

- [ ] `tests/{unit,flow,agent,e2e,live}/` all exist with tests in each.
- [ ] `tests/regression/` and `tests/integration/` no longer exist.
- [ ] 12 fixture anchors present under `tests/fixtures/builders/` (6 positive + 6 failure).
- [ ] All 12 fixtures have matching `expected/<name>.json`.
- [ ] No `.xlsx` files committed under `tests/fixtures/`.
- [ ] Full non-live suite passes: `.venv/Scripts/python.exe -m pytest tests -q -m "not live"` → ≥154 passed.
- [ ] `docs/TESTING.md` exists with the 8 rules + cookbook + anti-patterns.
- [ ] `docs/SPEC.md` links to `docs/TESTING.md` from § Testing strategy.
- [ ] Design doc Status flipped to `Implemented`.
- [ ] No code comment/docstring references plan or task numbers.
