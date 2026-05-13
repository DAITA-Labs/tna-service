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

Agent failure tests should cover **four sub-categories** of irregular LLM
responses (each is its own scenario in the agent tier):

1. **LLM raises an exception** (transport / network failure).
2. **LLM returns wrong type for a field** (e.g., string when list expected) — Pydantic validation error.
3. **LLM returns dict missing required fields** — Pydantic uses field defaults.
4. **LLM returns dict with extra/unknown fields** — Pydantic config (`extra="ignore"`) silently drops them.

In all four sub-categories the agent must fall back to a safe default
(empty `CanonicalNameMap()`, empty `relevant_sheets` list, etc.) and NOT
propagate the exception.

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
