# Canvas Architecture — Tier 4: Field Components

> Detailed task steps written immediately before tier starts. Outline only.

**Goal:** Land per-canonical field components for all 11 identifiers + stages + metadata. Each component encapsulates one canonical's policy in a small focused module. Cross-cutting concerns (sibling resolution, single-canonical, stage-wins, cardinality, merge-alignment) live in `IdentifierArbiter`.

**Architecture:** See design spec §6. Five-step contract per component: `locate → filter → claim → arbitrate → emit`. Components run in parallel within the IdentifiersPhase; `IdentifierArbiter` runs after all of them to resolve cross-canonical conflicts. Each component branches internally on `layout.axes.pli_axis` to use either tabular or k:v extraction path.

**Eval expectation by end of Tier 4:** identifier recall ≥ 68%, precision ≥ 65% (parity with current experiments baseline). Tier 6 judges will push these higher.

**Depends on:** Tiers 0-3 (artifacts, tools, structure, workbook all available).

---

## Task overview

| PR | # | Task | Type |
|---|---|---|---|
| 4a | 1 | `app/components/_canonical_base.py` — `BaseCanonicalComponent` with 5-step contract | feat |
| 4b | 2 | `app/components/identifiers/io_number.py` (anchor field) | feat |
| 4b | 3 | `app/components/identifiers/quantity.py` (anchor field, mandatory) | feat |
| 4c | 4 | `app/components/identifiers/style_code.py` + `style_name.py` (siblings under STYLE) | feat |
| 4c | 5 | `app/components/identifiers/color_code.py` + `color_name.py` (+ bare-CODE rule) | feat |
| 4c | 6 | `app/components/identifiers/fabric_code.py` + `fabric_name.py` | feat |
| 4d | 7 | `app/components/identifiers/delivery_date.py` (with stage-wins) | feat |
| 4d | 8 | `app/components/identifiers/shipment_date.py` (with stage-wins) | feat |
| 4d | 9 | `app/components/identifiers/ex_fty_date.py` (with stage-wins) | feat |
| 4e | 10 | `app/components/identifiers/arbiter.py` — sibling resolution + single-canonical + stage-wins + cardinality + merge-alignment | feat |
| 4f | 11 | `app/components/stages/arena.py` | feat |
| 4f | 12 | `app/components/stages/band.py` | feat |
| 4f | 13 | `app/components/stages/column_typing.py` | feat |
| 4f | 14 | `app/components/stages/per_pli.py` | feat |
| 4g | 15 | `app/components/metadata/collector.py` | feat |
| 4g | 16 | `app/components/metadata/classifier.py` | feat |
| 4g | 17 | `app/components/metadata/per_pli_binder.py` | feat |

---

## Per-canonical spec checklist

Each per-canonical component test fixture covers (at minimum):
- Tabular layout extraction (DKN, MOPD)
- k:v layout extraction (63261, NEW) — where applicable
- Section-style extraction (GUESS, MAIN FALL) — where applicable
- Anti-pattern rejection
- Single-column arbitration when multiple candidates match
- Confidence scoring per finding
- Evidence trail populated

## Exit bar

- [ ] All 17 tasks complete; PRs 4a–4g merged
- [ ] `make_identifier_phase_pipeline()` factory exists; per-canonical components run in parallel
- [ ] `make_stage_phase_pipeline()` factory exists
- [ ] Canvas eval against `dataset/extracted_2`: identifier recall ≥ 68%, precision ≥ 65%
- [ ] No per-canonical component imports `app.pipelines.*` or another per-canonical component (cross-cutting concerns only via IdentifierArbiter)
- [ ] Each component subclasses `BaseCanonicalComponent`
- [ ] CODING_STANDARD §10 self-review on every file
- [ ] Master plan checklist updated with Tier 4 ✓

Detailed task steps to be written immediately before Tier 4 starts.
