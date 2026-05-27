# Canvas Architecture — Tier 3: Workbook Phase

> Detailed task steps written immediately before tier starts. Outline only.

**Goal:** Land `app/components/workbook/` — `Profiler`, `Clusterer`, `RoleClassifier`, `SheetSelector`, `PerClusterDispatcher`, `Aggregator`. End-to-end: given an `xlsx` workbook, partition sheets into clusters, classify each cluster as `pli_cluster` or `other_sheets`, and dispatch StructurePhase + Field phases per `pli_cluster`.

**Architecture:** See design spec §4. Signature = `NonBlankMask` + `DtypeFingerprint` + `LabelTextPositions`. Cluster threshold 0.8; inheritance threshold 0.95. Role classifier checks three signals: `has_date_cells ≥ 1 AND has_numeric_value_cells ≥ 1 AND (has_kv_blocks ≥ 1 OR has_header_band_with_id_aliases)`. Composite-key dedup at aggregator: `(io_number, style_code)`.

**Eval expectation:** multi-sheet workbooks (Eastman with 17 PLI sheets, 63261 with mixed-template sheets, MAIN FALL #1 with 3 different sheets) correctly clustered. Cluster routing visible in logs. No extraction change yet (Tier 4 wires field components).

**Depends on:** Tier 2 (StructurePhase available so we can compute `has_kv_blocks` / `has_header_band` per sheet during role classification).

---

## Task overview

| PR | # | Task | Type |
|---|---|---|---|
| 3a | 1 | `app/components/workbook/profiler.py` — compute SheetSignature per sheet | feat |
| 3a | 2 | `app/components/workbook/signature.py` — similarity scoring | feat |
| 3a | 3 | `app/components/workbook/clusterer.py` — union-find grouping by similarity ≥ 0.8 | feat |
| 3a | 4 | `app/components/workbook/role_classifier.py` — pli_cluster | other_sheets | feat |
| 3a | 5 | `app/components/workbook/sheet_selector.py` — drop other_sheets | feat |
| 3b | 6 | `app/components/workbook/anchor_picker.py` — pick template anchor per cluster | feat |
| 3b | 7 | `app/components/workbook/dispatcher.py` — per-cluster pipeline dispatch | feat |
| 3b | 8 | `app/components/workbook/aggregator.py` — union + composite-key dedup | feat |
| 3b | 9 | `app/components/workbook/_phase.py` — WorkbookPhase orchestrator | feat |

---

## Exit bar

- [ ] All 9 tasks complete; PRs 3a–3b merged
- [ ] `make_workbook_pipeline()` factory in `app/pipelines/canvas/workbook.py` runnable in isolation
- [ ] Smoke tests on `dataset/`: Eastman → 1 cluster of 17, 63261 → 2 clusters of 1 each, MAIN FALL #1 → 3 clusters (one per template sheet)
- [ ] CODING_STANDARD §10 self-review on every file
- [ ] Master plan checklist updated with Tier 3 ✓

Detailed task steps to be written immediately before Tier 3 starts.
