# Test strategy — design

**Date:** 2026-05-13
**Status:** Approved, ready for implementation plan

## Problem

The current test corpus (154 passing tests across `tests/unit/`, `tests/integration/`, `tests/regression/`, `tests/repositories/`) grew incrementally and is now heterogeneous:

- **Test mechanics are inconsistent.** Some tests build synthetic in-memory workbooks inline; some load real xlsx files from `dataset/`; some are pure-logic tests with no workbook at all. Each test that needs a sample sheet rebuilds it from scratch in code.
- **Fixtures are not reusable.** The same "tabular with totals" or "vertical merge with children" shape is rebuilt by hand in many tests. Each rebuild is a chance to drift.
- **Failure-mode coverage is sparse.** Most tests cover happy paths. Failure cases — corrupted plans, ambiguous identity columns, agents returning invalid JSON, total rows without markers — are tested in only a few places, ad hoc.
- **Agent tests are smoke-only.** Each agent test asserts the `AgentSpec` loads. None exercise the agent under controlled inputs to lock its observed behaviour.
- **Live regression overlaps integration.** `tests/regression/` and `tests/integration/test_e2e_live.py` both run the real pipeline against the dataset, with different naming and slightly different assertion shapes.
- **No written conventions.** The next contributor has no document explaining where to put a new test or what shape a fixture should take.

Result: adding coverage is slow, regressions are easy to introduce, and the test layout doesn't communicate the system's structure.

## Goal

Establish a uniform, scalable test strategy with five clearly-bounded tiers, fixture-driven scenarios, first-class failure cases, and written conventions. Migrate the existing 154 tests onto the strategy.

## Non-goals

- Adding new feature coverage beyond what's already implicitly tested. (New scenarios for failure modes are explicitly in scope — but no new product features.)
- Changing how production code is structured. The new tests assert the same behaviours the existing tests assert; only the mechanics change.
- Changing the eval harness. Evals stay in `evals/`, separate from `tests/`.
- Adding test-only dependencies beyond what already exists (`pytest`, `openpyxl`, `pydantic`).

## Design

### Five-tier taxonomy

```
tests/
├── unit/    # one det function, no fixture (inline assertions)
├── flow/    # 2+ det functions chained, fixture-driven
├── agent/   # single LLM agent + FakeLLM, fixture-driven
├── e2e/     # full extract() pipeline + FakeLLM, fixture-driven
└── live/    # real Anthropic API + real dataset/*.xlsx, marked @pytest.mark.live
```

| Tier | LLM | Fixture | Typical assertion target |
| --- | --- | --- | --- |
| unit | none | none (inline) | direct return value of a function |
| flow | none | required | intermediate artifact (SheetPlan, validator Findings, list[PLI]) |
| agent | FakeLLM | required | agent's processed output (`hints`, `verdict`, `name_map`) |
| e2e | FakeLLM | required | final `ExtractionResult` |
| live | real Anthropic | real xlsx | tolerant range assertions, must-have subsets |

Each tier has a single, clear job. A test that crosses two tiers (e.g., "exercise the planner + run extract under FakeLLM") belongs in the deeper of the two.

### Fixture authoring pattern

Every fixture is two files:

```
tests/fixtures/builders/<scenario>.py    # Python module exporting build(wb: Workbook) -> None
tests/fixtures/expected/<scenario>.json  # tier-keyed assertions
```

The builder is the readable spec — what cells, merges, and structure the scenario exhibits. The expected.json declares what each tier should observe. No binary xlsx files in the repo: the pytest fixture materializes the workbook into `tmp_path` per test.

Builder example:

```python
# tests/fixtures/builders/sheet_per_pli_clean.py
"""3-sheet workbook where each sheet is a single PLI (Family 5 layout)."""
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
        from datetime import datetime
        ws["C9"] = datetime(2026, 3, 1); ws["D9"] = datetime(2026, 3, 5)
```

For synthetic-plan failure fixtures (e.g., a deliberately-corrupt `SheetPlan` that bypasses the planner), the builder exports `build_plan() -> SheetPlan` instead of `build(wb)`. The fixture loader detects which is present.

### `FixtureCase` + `@fixture_case` decorator

```python
# tests/fixtures/case.py
from dataclasses import dataclass
from pathlib import Path
import pytest
from app.models.workbook import WorkbookCtx


@dataclass(frozen=True)
class FixtureCase:
    name: str
    ctx: WorkbookCtx
    xlsx_path: Path
    _expected: dict

    @property
    def sheets(self) -> list[str]: ...
    @property
    def sheet(self) -> str:  # default = first sheet
        ...
    @property
    def description(self) -> str: ...

    def expectations(self, tier: str) -> dict:
        """Tier-specific block. Raises AssertionError if the tier section is absent."""

    def failure_expectations(self) -> dict | None: ...
    def is_failure_case(self) -> bool: ...
    def fake_llm_responses(self) -> dict: ...


def fixture_case(*names: str):
    """pytest.mark.parametrize sugar.

    @fixture_case("tabular_simple", "tabular_with_totals")
    def test_x(fixture):
        ...
    """
    return pytest.mark.parametrize("fixture", names, indirect=True, ids=list(names))
```

The `fixture` pytest fixture (in `tests/fixtures/conftest.py`) resolves a fixture name to a `FixtureCase`:

1. Imports `tests.fixtures.builders.<name>`.
2. Builds a fresh `Workbook` and runs `build(wb)`.
3. Saves to `tmp_path / "<name>.xlsx"` (unique per test).
4. Loads `tests/fixtures/expected/<name>.json`.
5. `register_workbook(xlsx_path)` → fresh ctx.
6. `clear_cache()` on setup AND teardown.

### Expected.json shape

```json
{
  "fixture": "<name>",
  "description": "<one-line>",
  "layer_expectations": {
    "flow": { "pli_mode": "row_per_pli", "anchor_count": 2, "child_count": 5, ... },
    "agent": {
      "plan_reviewer": { "canned_response": { ... }, "expected_processed_verdict": "looks_correct" }
    },
    "e2e": {
      "fake_llm_responses": { "SheetClassifierOutput": {...}, "CanonicalNameMap": {...}, ... },
      "pli_count": 7,
      "io_numbers": ["1063", "1063", "1063", "1063", "1064", "1064", "1064"]
    },
    "live": { "pli_count_min": 7, "must_have_io_numbers": ["1063", "1064"] }
  },
  "failure_expectations": null
}
```

For failure cases, `failure_expectations` is populated:

```json
"failure_expectations": {
  "category": "planner_ambiguity",
  "fires_layout_hinter": true,
  "expected_warning_check": "pli_count_sanity",
  "graceful_degradation": true
}
```

Tier sections are independent. A fixture only declares what it'll be used to test. Missing sections raise a clear AssertionError when a test asks for them.

### Failure case organization

Failure-case fixtures live alongside positive fixtures in `tests/fixtures/builders/`, with `failure_expectations` populated in their expected.json. Naming convention: `<feature>_<failure_mode>.py`.

Six failure families, one anchor fixture each:

| Category | Anchor fixture | What it proves |
|---|---|---|
| Input validation | `workbook_only_title_row.py` | Pipeline returns `ExtractionResult(plis=[], warnings=[...])` — doesn't crash. |
| Planner ambiguity | `tabular_corrupt_no_identity_col.py` | LayoutHinter fires; PLI count is 0 with a sanity warning. |
| Plan invariant violation | `plan_invariant_dangling_anchor.py` (synthetic — uses `build_plan()`) | `validate_invariants` emits ERROR. |
| Apply-level mismatch | `apply_name_map_missing_required.py` | `apply_plan` raises typed error, orchestrator converts to Warning. |
| Agent failure | `agent_returns_invalid_json.py` | FakeLLM raises parse error; pipeline continues with fallback. |
| Data anomaly | `stage_band_low_date_density.py` | Tier 2 plan validator emits `date_band_density` warning. |

Failure tests assert on *degradation behaviour* (Warning emitted, PLIs dropped, validator findings), not on raised exceptions — unless the contract explicitly is "raise."

### Test isolation guarantees

- Default pytest scope is `function` — the `fixture` pytest fixture reruns per test.
- Each test gets a unique `tmp_path` → unique xlsx_path → unique `WorkbookCtx`.
- `clear_cache()` runs on setup and teardown of every fixture-based test.
- `pytest-xdist` parallelization is safe (process-per-worker, each worker has its own cache).
- No module-level mutable state in tests.

Anti-patterns explicitly disallowed in the rules doc:
- Promoting `fixture` to session scope.
- Direct `register_workbook()` calls in fixture-using tests.
- Module-level shared state across tests.
- Same-filename collisions across builders (the loader uses `f"{name}.xlsx"` so names are intrinsically unique).

### FakeLLM helper

```python
# tests/fixtures/fake_llm.py
class FakeLLM:
    """LLMProvider stub that returns canned values keyed by output schema name."""

    def __init__(self, canned: dict):
        self._canned = canned

    def complete_with_schema(self, system, user, output_schema, tool_name=None):
        name = output_schema.__name__
        if name not in self._canned:
            raise AssertionError(
                f"FakeLLM has no canned response for schema {name!r}. "
                f"Available: {list(self._canned)}"
            )
        return output_schema(**self._canned[name])
```

`agent/` tests instantiate FakeLLM with the relevant agent's canned response. `e2e/` tests instantiate it with `fixture.fake_llm_responses()` covering every schema the pipeline will request.

## Migration plan

### Phased migration

**Phase A — Scaffolding (no behaviour change)**
- Create `tests/fixtures/{builders,expected}/` directories.
- Add `tests/fixtures/case.py`, `tests/fixtures/fake_llm.py`, `tests/fixtures/conftest.py`.
- Create empty `tests/flow/`, `tests/agent/`, `tests/e2e/`, `tests/live/` directories.
- Existing 154 tests continue to pass.

**Phase B — Build the fixture pool**
- 6 positive anchors: `sheet_per_pli_clean`, `row_per_pli_with_merges`, `section_per_pli_two_blocks`, `tabular_simple`, `tabular_with_totals`, `tabular_repeat_header`.
- 6 failure anchors: `tabular_corrupt_no_identity_col`, `workbook_only_title_row`, `plan_invariant_dangling_anchor`, `apply_name_map_missing_required`, `agent_returns_invalid_json`, `stage_band_low_date_density`.
- Each = one builder + one expected.json.

**Phase C — Reorganize by simple moves**
- `tests/regression/test_*.py` → `tests/live/`.
- `tests/integration/test_e2e_live.py` → `tests/live/test_dataset_acceptance.py`.
- `tests/integration/test_acceptance_extensibility.py` → `tests/unit/structure/test_layout.py`.
- Delete now-empty `tests/regression/`, `tests/integration/`.

**Phase D — Rewrite composite tests as fixture-driven flow tests**
- `tests/unit/applier/test_apply_plan_{row,sheet_is,section}_per_pli.py` → `tests/flow/test_apply_plan_*.py` using fixtures.
- `tests/unit/planner/test_plan.py` → `tests/flow/test_planner_pipeline.py` using fixtures.

**Phase E — Migrate agent tests to behaviour tests**
- `tests/unit/agents/test_*.py` → `tests/agent/test_*.py`. Replace smoke tests with FakeLLM-driven behaviour assertions.

**Phase F — Add the missing failure-case tests**
- One test per failure category, parametrized over the anchor fixture.

**Phase G — Write the rules doc**
- `docs/TESTING.md` codifies the conventions.
- `docs/SPEC.md` § Testing strategy links to it.

**Phase H — Cleanup & verify**
- Full suite passes (154+).
- `pytest --collect-only` confirms every test landed in the right tier.
- `pytest -m live` passes against real dataset.

### Test-by-test relocation table

| Current location | New location | Mode |
|---|---|---|
| `tests/unit/enums/*` | `tests/unit/enums/` | Stay |
| `tests/unit/models/*` | `tests/unit/models/` | Stay |
| `tests/unit/test_agent_base.py`, `test_artifacts.py`, `test_config.py` | `tests/unit/` | Stay |
| `tests/unit/applier/test_apply_plan_no_llm_imports.py` | `tests/unit/applier/` | Stay |
| `tests/unit/applier/test_apply_plan_{row,sheet_is,section}_per_pli.py` | `tests/flow/` | Rewrite |
| `tests/unit/planner/test_surveyor.py`, `test_row_classifier.py`, `test_kv_anchor_detector.py`, `test_block_segmenter.py`, `test_stage_band_detector.py` | `tests/unit/planner/` | Stay |
| `tests/unit/planner/test_plan.py` | `tests/flow/test_planner_pipeline.py` | Rewrite |
| `tests/unit/agents/test_*` | `tests/agent/` | Rewrite |
| `tests/unit/validation/test_plan_invariants.py`, `test_plan_statistics.py` | `tests/unit/validation/` | Stay |
| `tests/unit/validation/test_source_header.py`, `test_coverage_dropout.py` | `tests/unit/validation/` | Stay |
| `tests/repositories/*` | `tests/unit/repositories/` | Rename only |
| `tests/integration/test_acceptance_extensibility.py` | `tests/unit/structure/test_layout.py` | Rename only |
| `tests/integration/test_extraction_pipeline.py` | `tests/e2e/` | Rewrite |
| `tests/integration/test_e2e_live.py` | `tests/live/test_dataset_acceptance.py` | Rename only |
| `tests/regression/test_christian_berg.py`, `test_new_job_tna.py` | `tests/live/` | Rename only |

## Testing rules (the `docs/TESTING.md` content)

Eight rules. Each enforceable by code review or pytest itself.

1. **Pick the tier first.** Decision table in the doc.
2. **One fixture = one builder + one expected.json.** Use `@fixture_case` to consume.
3. **Fixtures stay minimal.** Build only what the test needs.
4. **Expected.json is keyed by tier.** Missing tier = explicit AssertionError.
5. **Failure cases follow the same shape.** Assert on degradation, not on raised exceptions.
6. **Agent tests use canned LLM responses.** Don't call real LLM in `agent/` tier.
7. **Use `@fixture_case`, never `register_workbook` directly in fixture-using tests.**
8. **Run pattern documented.** `pytest tests -q` (non-live), `pytest tests -m live -q` (live).

Plus an anti-patterns list and a "cookbook for adding a new layout family" walkthrough.

## Acceptance criteria

- All 154+ existing tests still pass after migration.
- `tests/` has the new 5-tier layout with no leftover empty or misnamed directories.
- 12+ fixture anchors authored (6 positive + 6 failure), each loadable via the `fixture` pytest fixture.
- Adding a new layout family is one builder + one expected.json — no test-code changes needed for an existing parametrized test to pick it up.
- Failure-case coverage exists for all six failure families.
- `docs/TESTING.md` exists and reflects the strategy.
- `docs/SPEC.md` § Testing strategy points at `docs/TESTING.md`.
- `pytest -m live` passes against the real dataset.
- No xlsx files committed under `tests/fixtures/` (binaries belong only in `dataset/`).
- Documentation update is the final step (after impl + tests + evals green), per the user's standing preference.

## Open questions deferred to the implementation plan

- Final list of positive fixtures. The 6 anchors are confirmed; secondary fixtures (e.g., `tabular_with_section_titles`, `vertical_merge_partial`) can be added as we author the migration.
- Exact `FakeLLM` semantics for cases where the pipeline requests a schema not in `canned` — currently the design says raise `AssertionError`; could relax to "return empty schema instance" if it makes e2e tests less brittle. Decide during Phase E.
- Whether `tests/unit/structure/test_layout.py` (the directory-layout invariants test, currently `test_acceptance_extensibility.py`) should be kept long-term or replaced by linter rules. Defer.
