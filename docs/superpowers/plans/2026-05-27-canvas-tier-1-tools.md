# Canvas Architecture — Tier 1: Tools

> Detailed task steps written immediately before tier starts. Outline only.

**Goal:** Land all canvas-tool primitives under `app/tools/canvas/`. Tools are pure functions, `@tool`-decorated, no orchestration logic, no LLM calls. Each is independently testable.

**Architecture:** See `docs/superpowers/specs/2026-05-27-canvas-architecture-design.md` §5.2. Tools are the deterministic substrate — they read a `GridCanvas` and emit typed records into a `StructureBag`. Detectors are parallel-safe (no inter-detector dependencies).

**Eval expectation:** zero change to canvas eval. Tools are not yet consumed by any extractor.

**Depends on:** Tier 0 complete (specs + artifacts in `app/`).

---

## Task overview

| PR | # | Task | Type |
|---|---|---|---|
| 1a | 1 | Port `build_canvas` from `experiments/p3_visual/canvas_probe/build_canvas.py` to `app/tools/canvas/build.py` | feat |
| 1a | 2 | Port `find_around_cell` / `find_around_range` to `app/tools/canvas/around.py` | feat |
| 1a | 3 | Port `query_spec` / `query_phase` / `query_all` + word-boundary rules + reject phrases to `app/tools/canvas/query.py` | feat |
| 1b | 4 | `app/tools/canvas/strips_date.py` — DateStrip detector (vertical and horizontal) | feat |
| 1b | 5 | `app/tools/canvas/strips_numeric.py` — IntStrip (magnitude-tagged) + FloatStrip | feat |
| 1b | 6 | `app/tools/canvas/strips_text.py` — SameLengthStrip + LongTextStrip | feat |
| 1c | 7 | `app/tools/canvas/strips_visual.py` — ColorStrip + BoldStrip + BorderedBox | feat |
| 1c | 8 | `app/tools/canvas/strips_merge.py` — MergeSpan + NonMergedStrip + MergedColumnStrip | feat |
| 1c | 9 | `app/tools/canvas/kv_block.py` — KvBlockDetector (bold/filled label + adjacent value gate) | feat |
| 1c | 10 | `app/tools/canvas/repeating_group.py` — RepeatingRowGroup detector by signature | feat |
| 1d | 11 | `app/tools/canvas/plan_marker.py` — PlanMarkerCluster detector | feat |
| 1d | 12 | `app/tools/canvas/dtype_profiles.py` — RowDtypeProfile + ColDtypeProfile | feat |

---

## Exit bar

- [ ] All 12 tasks complete; all 4 PRs (1a–1d) merged into `canvas-architecture`
- [ ] Each tool tested against fixture sheets from `dataset/` (at minimum: DKN, 63261, GUESS, FA26)
- [ ] `pytest tests/unit/tools/canvas/ -v` all green
- [ ] CODING_STANDARD §10 self-review on every new file
- [ ] No imports from `app.components`, `app.pipelines`, or `app.agents` in any tool module
- [ ] Master plan checklist updated with Tier 1 ✓

Detailed task steps to be written immediately before Tier 1 starts.
