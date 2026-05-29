# Phase 9 — Eval Comparison + Endpoint Swap

> **Scaffold plan.** Full bite-sized steps land after Phase 8 merges.

**Goal:** Run the canvas eval against both `/extract_canvas` (current) and `/extract_canvas_v2` (new plan-driven chain). When v2 matches or beats v1 across every labelled family, promote v2 to be the canonical `/extract_canvas` and deprecate v1.

**Architecture:** No new component code; the work is eval harness invocation + result diffing + a router swap.

**Spec sections:** §11 phase 10.

**Depends on:** Phase 8 merged.

---

## File map

**Modify (no creation):**
- `app/routers/extract_canvas.py` — swap the chain it dispatches to from v1 to v2 (one-line change once eval is green)
- `app/routers/extract_canvas_v2.py` — mark as deprecated; redirect to `/extract_canvas` (or delete after one release)
- `ARCHITECTURE.md` — note that `/extract_canvas` now runs the plan-driven chain
- `docs/SPEC.md` — update endpoint description if behavior changed externally (it should not have)

---

## Task outline

1. **Run canvas eval against v1**, capture per-family scores into `evals/results/v1_baseline.json`.
2. **Run canvas eval against v2**, capture into `evals/results/v2_candidate.json`.
3. **Diff** — produce a per-family comparison table; for every family where v2 < v1, open an issue against the relevant policy/picker. Do not swap until v2 ≥ v1 everywhere.
4. **Swap the router** — `/extract_canvas` now dispatches to v2's chain. Keep v1 reachable at `/extract_canvas_v1` for one release in case of rollback.
5. **Add an integration test** that hits `/extract_canvas` and asserts the new chain runs (e.g., a `CanvasPlan` artifact appears in the capture output).

---

## Validation

- v2 ≥ v1 on every labelled family.
- `/extract_canvas` runs the new chain in production-style integration tests.
- Rollback path (`/extract_canvas_v1`) verified.
