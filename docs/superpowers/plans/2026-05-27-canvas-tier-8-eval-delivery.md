# Canvas Architecture — Tier 8: Eval + Delivery

> Detailed task steps written immediately before tier starts. Outline only.

**Goal:** Lift the canvas eval harness from `experiments/canvas_eval/` to `app/eval/`. Land integration smoke tests against `dataset/extracted_2`. Retire `experiments/p3_visual/canvas_probe/`. Update docs. Merge `canvas-architecture` → `main`.

**Architecture:** Eval harness becomes a first-class part of the app, runnable via `make eval-canvas`. Integration tests in `tests/integration/canvas/` execute the full canvas pipeline against a curated subset of `dataset/extracted_2` and assert per-canonical recall ≥ targets.

**Eval expectation:** canvas beats legacy by ≥5pts on both metrics across the full dataset. Final merge to main unlocked.

**Depends on:** Tier 7 (pipelines + router complete).

---

## Task overview

| PR | # | Task | Type |
|---|---|---|---|
| 8a | 1 | `app/eval/canvas_eval.py` — lifted from `experiments/canvas_eval/score.py`, refactored under CODING_STANDARD | feat |
| 8a | 2 | `app/eval/__init__.py` — re-exports | feat |
| 8a | 3 | `tests/integration/canvas/test_extracted_2_smoke.py` — full pipeline smoke per file | test |
| 8a | 4 | `Makefile` target `make eval-canvas` | chore |
| 8a | 5 | `docs/TESTING.md` — canvas eval section | docs |
| 8a | 6 | `docs/SPEC.md` — Findings shape + Verdict shape documented if exposed | docs |
| 8a | 7 | `docs/ARCHITECTURE.md` — promote "in development" canvas section to "implemented" | docs |
| 8b | 8 | `git rm -rf experiments/p3_visual/canvas_probe/` OR move to `docs/superpowers/archive/p3_canvas_probe/` for reference | chore |
| 8b | 9 | `git rm -rf experiments/canvas_eval/` | chore |
| 8b | 10 | `docs/JOURNEY.md` — canvas architecture milestone entry | docs |
| 8b | 11 | Flip `use_canvas_path` tuning default to True; verify all eval files pass | chore |
| 8b | 12 | Final merge `canvas-architecture` → `main` (squashed or merge-commit per maintainer preference) | merge |

---

## Final merge bar (canvas-architecture → main)

The merge is unlocked when:
- [ ] Canvas eval beats SheetRowPlanner eval on `dataset/extracted_2` by ≥5pts identifier recall AND ≥5pts identifier precision AND no stage regression on any file
- [ ] All 252 + new tests pass
- [ ] Integration smoke tests against the full eval dataset complete in <5 minutes (no LLM calls — judges use FakeLLM)
- [ ] Real-LLM eval run (env-gated) confirms judge contribution
- [ ] `docs/ARCHITECTURE.md`, `docs/SPEC.md`, `docs/TESTING.md`, `docs/JOURNEY.md` all updated
- [ ] ADR-0008 + ADR-0009 status flipped to "Accepted (implemented)"
- [ ] Master plan checklist all checkboxes ticked

## Exit bar

- [ ] All 12 tasks complete
- [ ] Canvas path is the default extraction path on main
- [ ] Legacy SheetRowPlanner path either retired or kept as `app/pipelines/extract_legacy.py` for one release as a fallback
- [ ] Branch `canvas-architecture` deleted from origin after merge

Detailed task steps to be written immediately before Tier 8 starts.
