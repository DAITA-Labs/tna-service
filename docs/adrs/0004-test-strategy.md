# 0004 — Test strategy (five-tier, fixture-driven)

**Date:** 2026-05-13
**Status:** Accepted

## Context

Before the test strategy overhaul (~154 tests), the test corpus had grown incrementally and was heterogeneous:

- Test mechanics were inconsistent: some tests built synthetic workbooks inline; some loaded real xlsx from `dataset/`; some were pure-logic.
- Fixtures were not reusable: the same "tabular with totals" or "vertical merge with children" shape was rebuilt from scratch in multiple tests, each rebuild a chance to drift.
- Failure-mode coverage was sparse. Most tests covered happy paths; failure cases were ad hoc.
- Agent tests were smoke-only: each asserted the `AgentSpec` loaded, but none exercised the agent under controlled inputs.
- `tests/regression/` and `tests/integration/test_e2e_live.py` overlapped with no clear separation.
- No written conventions existed for where to put a new test or what shape a fixture should take.

## Decision

Establish a five-tier taxonomy with fixture-driven scenarios, a `FakeLLM` stub for deterministic agent testing, and written conventions in `docs/TESTING.md`.

**Five tiers:**

```
tests/
  unit/    # one det function, no fixture (inline assertions)
  flow/    # 2+ det functions chained, fixture-driven
  agent/   # single LLM agent + FakeLLM, fixture-driven
  e2e/     # full extract() pipeline + FakeLLM, fixture-driven
  live/    # real Anthropic API + real dataset/*.xlsx, @pytest.mark.live
```

**Fixture pattern:** every scenario is `tests/fixtures/builders/<name>.py` (Python module, `build(wb) -> None`) + `tests/fixtures/expected/<name>.json` (tier-keyed assertions). No binary xlsx committed under `tests/fixtures/`. Fixtures are materialised into `tmp_path` per test run.

**`FixtureCase` + `@fixture_case` decorator:** pytest parametrize sugar that resolves a fixture name to a `FixtureCase` dataclass wrapping the `WorkbookCtx`, expected data, and canned LLM responses. `clear_cache()` runs on setup and teardown.

**`FakeLLM` stub:** returns canned values keyed by output schema name; raises `AssertionError` if a requested schema is missing. Agent tests use it to lock observed agent behaviour without calling the real API.

**Six failure families:** input validation, planner ambiguity, plan invariant violation, apply-level mismatch, agent failure, data anomaly. Each has one anchor fixture. Tests assert on degradation behaviour (Warning emitted, PLIs dropped, validator findings), not on exceptions unless the contract explicitly is "raise."

Implemented across ~29 tasks (commits 2026-05-13). Test count grew from ~154 to ~209.

## Consequences

**Easier:**
- Adding a new layout family: one builder + one expected.json; existing parametrized tests pick it up automatically.
- Failure-mode coverage exists for all six failure families.
- Agent tests are now behaviour tests (locked with FakeLLM) rather than smoke tests.
- `pytest tests -q -m "not live"` is a hard gate; `pytest tests -m live` is a separate expensive pass.

**Harder / constrained:**
- Every fixture-using test must go through `@fixture_case` — not `register_workbook()` directly. This is a convention that must be enforced via code review.
- `FakeLLM` canned responses must be kept current when agent output schemas evolve.

**What we gave up:**
- Free-form test layout. The tiered structure is a constraint that trades flexibility for predictability.

## Alternatives considered

- **Session-scoped fixtures.** Rejected: causes cross-test contamination via `WorkbookCtx` cache. Function scope is mandatory.
- **Binary xlsx fixtures under `tests/`** committed to git. Rejected: binary files bloat the repo and make diffs unreadable. Builders produce identical workbooks deterministically.
- **Property-based testing (Hypothesis).** Evaluated but deferred: the input space is too structured (valid xlsx shapes) and the oracle (correct PLI extraction) is too hard to express as a predicate without effectively writing a second extractor.
