# Canvas Architecture — Tier 2: Structure Phase

> Detailed task steps written immediately before tier starts. Outline only.

**Goal:** Land `app/components/structure/` — the pattern-detector components, semantic resolvers, `AxisInferrer`, and `LayoutComposer`. End-to-end: given a `GridCanvas`, emit a `LayoutHint` ready for field components to consume.

**Architecture:** See design spec §5. Pattern detectors run in parallel (independent), populate a `StructureBag`. Semantic resolvers form a DAG (HeaderBand → DataRowRange → StageArena → StageBand → SubfieldCluster). `AxisInferrer` runs after resolvers and emits `LayoutAxes`. `LayoutComposer` bundles everything into `LayoutHint`. Two-pass dependency: `StageArenaResolver` runs orientation-agnostic in pass 1; pass 2 refines with axis info.

**Eval expectation:** LayoutHints visualisable for every file in `dataset/extracted_2`. No extraction wired yet — this tier just produces the typed substrate that Tier 4 consumes.

**Depends on:** Tier 1 (tools available).

---

## Task overview

| PR | # | Task | Type |
|---|---|---|---|
| 2a | 1 | `app/components/structure/pattern_detectors/__init__.py` — re-export tool wrappers as Haystack components | feat |
| 2a | 2 | `app/components/structure/resolvers/header_band.py` | feat |
| 2a | 3 | `app/components/structure/resolvers/data_row_range.py` | feat |
| 2a | 4 | `app/components/structure/resolvers/stage_arena.py` | feat |
| 2a | 5 | `app/components/structure/resolvers/stage_band.py` | feat |
| 2a | 6 | `app/components/structure/resolvers/subfield_cluster.py` | feat |
| 2a | 7 | `app/components/structure/resolvers/section_boundary.py` | feat |
| 2b | 8 | `app/components/structure/axis_inferrer.py` (PliAxis + StageAxis + SubfieldAxis) | feat |
| 2b | 9 | `app/components/structure/layout_composer.py` (assembles `LayoutHint`, pre-narrows candidate_columns/rows/kv_blocks) | feat |
| 2c | 10 | `app/components/structure/anchor_picker.py` | feat |
| 2c | 11 | `app/components/structure/inheritance_verifier.py` (≥90% header-cell verification) | feat |
| 2c | 12 | `app/components/structure/_phase.py` — StructurePhase orchestrator | feat |

---

## Exit bar

- [ ] All 12 tasks complete; PRs 2a–2c merged
- [ ] `make_structure_pipeline()` factory in `app/pipelines/canvas/structure.py` exists and is testable in isolation
- [ ] Running structure phase on each file in `dataset/extracted_2` produces a `LayoutHint` whose declared axes match the GT plan's pli_mode field (manual spot-check on 5+ files)
- [ ] CODING_STANDARD §10 self-review on every file
- [ ] No imports of `app.pipelines.*` from any structure component
- [ ] Master plan checklist updated with Tier 2 ✓

Detailed task steps to be written immediately before Tier 2 starts.
