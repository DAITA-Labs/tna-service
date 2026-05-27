# Canvas Architecture — Tier 7: Pipelines + Router

> Detailed task steps written immediately before tier starts. Outline only.

**Goal:** Compose every layer's components into the final canvas pipeline via `make_*_pipeline()` factories. Land the router that decides per sheet whether to use canvas or legacy SheetRowPlanner path. Land the Reconciler that emits PLI JSON from canvas findings.

**Architecture:** See design spec §12. Style B — primary entry `make_canvas_pipeline()` mega-factory composing sub-factories. Sub-factories (`make_workbook_pipeline`, `make_structure_pipeline`, `make_identifier_phase_pipeline`, `make_stage_phase_pipeline`, `make_metadata_phase_pipeline`) exist for testability. Router uses tuning flag (initially `use_canvas_path=False`) to default to legacy; flip to True for parity testing.

**Eval expectation:** end-to-end PLI JSON output via canvas path. Tunable per-sheet routing. Canvas path beats legacy on ≥50% of files initially; bar to flip default is parity across the full dataset.

**Depends on:** Tiers 2-6 (all phase components exist).

---

## Task overview

| PR | # | Task | Type |
|---|---|---|---|
| 7a | 1 | `app/pipelines/canvas/structure.py` — `make_structure_pipeline()` | feat |
| 7a | 2 | `app/pipelines/canvas/workbook.py` — `make_workbook_pipeline()` | feat |
| 7a | 3 | `app/pipelines/canvas/identifiers.py` — `make_identifier_phase_pipeline()` | feat |
| 7a | 4 | `app/pipelines/canvas/stages.py` — `make_stage_phase_pipeline()` | feat |
| 7a | 5 | `app/pipelines/canvas/metadata.py` — `make_metadata_phase_pipeline()` | feat |
| 7a | 6 | `app/pipelines/canvas/main.py` — `make_canvas_pipeline()` mega-factory | feat |
| 7a | 7 | `app/pipelines/router.py` — canvas vs legacy switch (tuning-flagged) | feat |
| 7b | 8 | `app/components/reconciler.py` — Findings → PLI JSON | feat |
| 7b | 9 | Wire router into existing `app/pipelines/extract.py` as the entry point | feat |

---

## Exit bar

- [ ] All 9 tasks complete; PRs 7a–7b merged
- [ ] Canvas pipeline runs end-to-end and emits the same PLI JSON shape as the legacy path
- [ ] Tuning flag `use_canvas_path` flips entire pipeline cleanly
- [ ] Per-sheet router decisions logged
- [ ] No pipeline imports any judge agent directly (judges only via `JudgeGateComponent`)
- [ ] No tool imports any component or pipeline
- [ ] CODING_STANDARD §10 self-review on every file
- [ ] Master plan checklist updated with Tier 7 ✓

Detailed task steps to be written immediately before Tier 7 starts.
